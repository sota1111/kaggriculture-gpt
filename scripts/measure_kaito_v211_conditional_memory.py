#!/usr/bin/env python3
"""Strict-future screen/confirm evaluation for SOT-2985."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import statistics
import tempfile
import time
from pathlib import Path

from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "candidates/kaito-v211-conditional-memory"
FOUNDATION = ROOT / "candidates/lonespear-care-production/agent.py"
ADAPTER = PACKAGE / "adapter.py"
SOURCE = PACKAGE / "source.json"
FIXTURE = ROOT / "tests/fixtures/kaito_v211_conditional_memory.json"
OUTPUT = ROOT / "docs/measurements/SOT-2981/SOT-2985-kaito-v211-conditional-memory.json"
CHAMPION = ROOT / "main.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_candidate(path: Path) -> None:
    source = json.loads(SOURCE.read_text())
    assert source["redistribution"] == "prohibited-fail-closed"
    assert source["implementation"] == "clean-room-public-condition-only"
    assert sha(FOUNDATION) == source["foundation_sha256"]
    foundation = FOUNDATION.read_text()
    assert foundation.count("def agent(obs):") == 1
    path.write_text(foundation.replace("def agent(obs):", "def _foundation_agent(obs):") + "\n\n" + ADAPTER.read_text())


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    dimensions = ("opponent", "lineage", "episode", "seed", "time_slice", "time_index")
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == f"kaggle-environments=={importlib.metadata.version('kaggle-environments')}",
        "source_license_hash_fixed": all(source.get(key) for key in ("source_url", "kernel_id", "notebook_sha256", "output_main_sha256", "output_archive_sha256", "license", "redistribution")),
        "license_fail_closed": source.get("license") == "UNSPECIFIED" and source.get("redistribution") == "prohibited-fail-closed",
        "upstream_bytes_excluded": not any((PACKAGE / name).exists() for name in ("upstream.py", "main.py", "submission.tar.gz", "notebook.ipynb")),
        "clean_room_independent": source.get("implementation") == "clean-room-public-condition-only" and source.get("default_enabled") is False,
        "same_seed_both_seats": all({r["seat"] for r in panel if r["seed"] == seed} == {0, 1} for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "strict_future_all_dimensions": all({r[key] for r in screen}.isdisjoint({r[key] for r in confirm}) for key in dimensions),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "confirm_sealed": fixture.get("confirm_policy") == "sealed-until-screen-pass",
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def static_audit(path: Path, source: dict) -> dict:
    tree = ast.parse(path.read_text())
    imports = set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Name):
            names.add(node.id.lower())
    forbidden = source["forbidden_runtime_features"]
    hits = sorted(feature for feature in forbidden if feature.replace(" ", "_").lower() in names)
    text = path.read_text()
    required_stdlib_only = imports <= {"collections", "copy", "heapq", "itertools", "json", "math", "random", "numpy", "scipy"} \
        and "except Exception" in text and "_HUNGARIAN = False" in text
    return {"imports": sorted(imports), "stdlib_only": required_stdlib_only,
            "optional_scientific_imports_fail_closed": "import numpy as _np" in text and "from scipy.optimize import linear_sum_assignment" in text and "_HUNGARIAN = False" in text,
            "forbidden_runtime_feature_hits": hits, "public_state_only": not hits}


def targeted_firing(module) -> dict:
    signature = {"workers": 1, "unlocks": [], "positions": [0, 0], "exposure": [3, 0, 0, 0, 0, 0, 0, 0]}
    familiar = dict(signature)
    unknown = {"workers": 99, "unlocks": ["UNKNOWN"], "positions": [99, 99], "exposure": [999] * 8}
    module._CM_MEMORY = [{"step": 24, "signature": signature}]
    action = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WOOL", 2], ["SELL", "MILK", 3]]}
    obs = {"player": 0, "step": 25, "farms": [{}, {}]}
    original = module._cm_signature
    try:
        module._cm_signature = lambda _farm: familiar
        hit = module._cm_apply(obs, action, 25)
        hit_telemetry = module.conditional_memory_telemetry()
        module._cm_signature = lambda _farm: unknown
        fallback = module._cm_apply(obs, action, 26)
        fallback_telemetry = module.conditional_memory_telemetry()
        module._CM_MEMORY = []
        module._cm_signature = lambda _farm: familiar
        miss = module._cm_apply(obs, action, 27)
        miss_telemetry = module.conditional_memory_telemetry()
    finally:
        module._cm_signature = original
    sell_multiset = lambda value: sorted(tuple(x) for x in value["market"] if x and x[0] == "SELL")
    return {"hit_fired": hit_telemetry["hit"] > 0, "miss_fired": miss_telemetry["miss"] > 0,
            "fallback_fired": fallback_telemetry["fallback"] > hit_telemetry["fallback"],
            "hit_reordered": hit["market"] != action["market"], "unknown_preserved_base": fallback == action,
            "sell_multiset_preserved": all(sell_multiset(row) == sell_multiset(action) for row in (hit, fallback, miss)),
            "memory_max_distance": module.MEMORY_MAX_DISTANCE}


def run(policy: str, agent_path: Path, identity: dict, cohort: str) -> dict:
    lineup = [str(agent_path), identity["opponent"]]
    if identity["seat"] == 1:
        lineup.reverse()
    started = time.perf_counter()
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
    env.run(lineup)
    elapsed = time.perf_counter() - started
    terminal, seat = env.steps[-1], identity["seat"]
    rewards = [float(state.reward or 0) for state in terminal]
    actions = [states[seat].action for states in env.steps if states[seat].action is not None]
    trace = hashlib.sha256(json.dumps(actions, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return {**identity, "cohort": cohort, "policy": policy, "reward": rewards[seat], "opponent_reward": rewards[1-seat],
            "margin": rewards[seat]-rewards[1-seat], "rank": 1 if rewards[seat] >= rewards[1-seat] else 2,
            "statuses": [str(state.status) for state in terminal], "steps": len(env.steps), "runtime_seconds": elapsed,
            "action_trace_sha256": trace}


def summary(rows: list[dict]) -> dict:
    margins = sorted(row["margin"] for row in rows)
    return {"episodes": len(rows), "mean_rank": statistics.fmean(row["rank"] for row in rows),
            "mean_margin": statistics.fmean(margins), "p20_margin": margins[0], "worst_margin": margins[0],
            "wins_or_ties": sum(row["rank"] == 1 for row in rows),
            "all_done": all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720 for row in rows),
            "max_runtime_seconds": max(row["runtime_seconds"] for row in rows)}


def evaluate(cohort: str, fixture: dict, candidate: Path) -> dict:
    rows = [run(policy, path, identity, cohort) for identity in fixture[cohort]
            for policy, path in (("candidate", candidate), ("champion", CHAMPION))]
    candidate_rows = [row for row in rows if row["policy"] == "candidate"]
    champion_rows = [row for row in rows if row["policy"] == "champion"]
    candidate_summary, champion_summary = summary(candidate_rows), summary(champion_rows)
    traces = {(r["episode"], r["seed"], r["seat"]): r["action_trace_sha256"] for r in champion_rows}
    delta = {key: candidate_summary[key] - champion_summary[key] for key in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")}
    return {"candidate": candidate_summary, "champion": champion_summary, "candidate_rows": candidate_rows,
            "champion_rows": champion_rows, "delta": delta,
            "paired_trace_divergences": sum(r["action_trace_sha256"] != traces[(r["episode"], r["seed"], r["seat"])] for r in candidate_rows)}


def gate(panel: dict) -> bool:
    return panel["candidate"]["all_done"] and panel["paired_trace_divergences"] == panel["candidate"]["episodes"] \
        and (panel["delta"]["mean_rank"] < 0 or panel["delta"]["mean_margin"] > 0) \
        and panel["delta"]["p20_margin"] >= 0 and panel["delta"]["worst_margin"] >= 0


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate(fixture, source)
    report = {"issue": "SOT-2985", "axis": "v21.1 conditional-memory clean-room whole agent",
              "preregistered_difference_from_v39": "Current-episode public opponent-state conditional SELL-order memory with ordinary-action fallback; no fixed sparse-history checkpoint continuation, calibrated upstream prototypes, identity inputs, or cross-episode memory.",
              "hypothesis": "Identity-free within-episode opponent-state memory can prioritize colliding existing SELL orders while preserving the coherent foundation and safely abstaining for unknown states.",
              "source": source, "checks": checks, "kaggle_submission": "NOT_PERFORMED",
              "champion": {"path": "main.py", "sha256": sha(CHAMPION), "modified": False},
              "public_score_used_for_selection": False}
    try:
        if not all(checks.values()):
            raise ValueError("preflight failed")
        with tempfile.TemporaryDirectory(prefix="sot2985-") as directory:
            candidate = Path(directory) / "main.py"
            build_candidate(candidate)
            module = load(candidate, "sot2985_candidate")
            report["candidate"] = {"build_sha256": sha(candidate), "static_audit": static_audit(candidate, source),
                                   "targeted_firing": targeted_firing(module), "default_enabled": False}
            if not report["candidate"]["static_audit"]["stdlib_only"] or not report["candidate"]["static_audit"]["public_state_only"] or not all(v for k, v in report["candidate"]["targeted_firing"].items() if k != "memory_max_distance"):
                raise ValueError("candidate contract failed")
            report["screen"] = evaluate("screen", fixture, candidate)
            report["screen_gate"] = "PASS" if gate(report["screen"]) else "FAIL"
            report["confirm"] = evaluate("confirm", fixture, candidate) if gate(report["screen"]) else {"consumed": False, "reason": "sealed after screen failure"}
            if gate(report["screen"]):
                report["confirm"]["consumed"] = True
            promoted = gate(report["screen"]) and gate(report["confirm"])
            report["runtime_contract"] = "PASS" if report["screen"]["candidate"]["all_done"] and (not report["confirm"].get("consumed") or report["confirm"]["candidate"]["all_done"]) else "FAIL"
            report["decision"] = "promoted-independent-hedge" if promoted else "rejected"
            report["passed"] = report["runtime_contract"] == "PASS" and report["candidate"]["targeted_firing"]["hit_fired"] and report["candidate"]["targeted_firing"]["miss_fired"] and report["candidate"]["targeted_firing"]["fallback_fired"]
    except Exception as error:
        report.update({"passed": False, "decision": "inconclusive", "reason": f"{type(error).__name__}: {error}"})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

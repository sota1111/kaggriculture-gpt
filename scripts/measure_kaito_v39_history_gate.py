#!/usr/bin/env python3
"""Fail-closed provenance, history-gate, and lineage holdout for SOT-2966."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import tarfile
import tempfile
import time
from collections import Counter
from math import ceil
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidates/kaito-v39-history-gate/source.json"
FIXTURE = ROOT / "tests/fixtures/kaito_v39_history_gate.json"
OUTPUT = ROOT / "docs/measurements/SOT-2962/SOT-2966-kaito-v39-history-gate.json"
CHAMPION = ROOT / "main.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    required_hashes = ("notebook_sha256", "main_py_sha256", "archive_sha256", "manifest_sha256")
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.4",
        "source_version_hashes_recorded": all(source.get(key) for key in required_hashes),
        "license_fail_closed": source.get("license") == "UNSPECIFIED"
            and source.get("redistribution") == "prohibited-fail-closed",
        "source_not_redistributed": not (ROOT / "candidates/kaito-v39-history-gate/agent.py").exists(),
        "default_off_independent": source.get("default_enabled") is False
            and "v39" not in CHAMPION.read_text().lower(),
        "history_checkpoints_complete": fixture.get("history_checkpoints") == [96, 120, 122, 132, 144],
        "same_seed_both_seats": all(
            {r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "screen_confirm_lineage_episode_seed_time_disjoint": all(
            {r[key] for r in screen}.isdisjoint({r[key] for r in confirm})
            for key in ("lineage", "episode", "seed", "time_index")),
        "chronological_confirm": max(r["time_index"] for r in screen)
            < min(r["time_index"] for r in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def acquire(directory: Path, source: dict) -> tuple[Path, dict]:
    supplied = os.environ.get("KAITO_V39_MAIN_PATH")
    if supplied:
        candidate, method = Path(supplied).resolve(), "pinned-local-artifact"
    else:
        subprocess.run(["kaggle", "kernels", "output", source["kaggle_ref"], "-p", str(directory)], check=True)
        candidate, method = directory / "main.py", "kaggle-api-transient-output"
    archive, manifest = candidate.parent / "submission.tar.gz", candidate.parent / "v39_manifest.json"
    hashes = {
        "main_hash_ok": sha256(candidate) == source["main_py_sha256"],
        "archive_hash_ok": archive.exists() and sha256(archive) == source["archive_sha256"],
        "manifest_hash_ok": manifest.exists() and sha256(manifest) == source["manifest_sha256"],
    }
    hashes["archive_member_ok"] = False
    if hashes["archive_hash_ok"]:
        with tarfile.open(archive, "r:gz") as bundle:
            member = bundle.extractfile("main.py")
            hashes["archive_member_ok"] = member is not None and hashlib.sha256(member.read()).hexdigest() == source["main_py_sha256"]
    imports = set()
    for node in ast.walk(ast.parse(candidate.read_text())):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return candidate, {"method": method, **hashes, "imports": sorted(imports),
        "stdlib_only": imports <= {"base64", "json", "sys", "types", "zlib"}}


def load_candidate(path: Path):
    name = "sot2966_v39_" + hashlib.sha1(str(time.time_ns()).encode()).hexdigest()
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def audit_router(module, fixture: dict) -> dict:
    planner, policy = module._V39_PLANNER, module._V39_POLICY
    calibration = policy.calibration
    fallback = calibration["fallback"]["config"]
    stage2 = calibration["stage2"]["config"]
    planner_names = set()
    for value in vars(planner).values():
        if callable(value) and hasattr(value, "__code__"):
            planner_names.update(value.__code__.co_names)
            planner_names.update(str(v) for v in value.__code__.co_consts if isinstance(v, str))
    forbidden = set(SOURCE.read_text() and json.loads(SOURCE.read_text())["forbidden_runtime_features"])
    forbidden_code_hits = sorted(name for name in forbidden if any(name.lower() in token.lower() for token in planner_names))
    unknown = {"opponent_layout": ["UNKNOWN"] * 75, "opponent_counts": [999.0] * 8,
        "opponent_actors": [99.0] * 3, "opponent_money": -999999.0,
        "opponent_unlocks": ["UNKNOWN"], "own_state": [999.0] * 10,
        "prices": [999.0] * 9, "inventory": [-999.0] * 9, "shops": {"UNKNOWN": 99}, "seat": 0}
    distance = min(planner.parts_distance(unknown, prototype["parts"], fallback["scheme"])
        for prototype in calibration["fallback"]["prototypes"])
    mutated = dict(unknown)
    mutated.update({"username": "mutated", "kernel slug": "mutated", "episode id": 999,
        "seed": 999, "private result": -999999, "future metadata": {"winner": 1}})
    mutated_distance = min(planner.parts_distance(mutated, prototype["parts"], fallback["scheme"])
        for prototype in calibration["fallback"]["prototypes"])
    # The policy initializes to base and only accepts an estimated override at
    # or below maximum_distance. An out-of-support state therefore abstains.
    route = "base" if distance > fallback["maximum_distance"] else "estimated"
    return {
        "checkpoints": list(planner.HISTORY_CHECKPOINTS),
        "checkpoints_match_manifest": list(planner.HISTORY_CHECKPOINTS) == fixture["history_checkpoints"],
        "fallback_maximum_distance": fallback["maximum_distance"],
        "stage2_maximum_distance": stage2["maximum_distance"],
        "unknown_state": {"distance": distance, "selected": route,
            "abstained_to_conservative_fallback": distance > fallback["maximum_distance"] and route == "base"},
        "forbidden_runtime_feature_code_hits": forbidden_code_hits,
        "public_state_only": not forbidden_code_hits,
        "private_future_metadata_mutation_invariant": mutated_distance == distance,
        "history_gate_present": "history" in planner_names and stage2.get("history_weight", 0) > 0,
    }


def summarize(rows: list[dict]) -> dict:
    margins = sorted(r["margin"] for r in rows)
    return {"episodes": len(rows), "mean_rank": sum(r["rank"] for r in rows) / len(rows),
        "mean_margin": sum(margins) / len(margins),
        "p20_margin": margins[max(0, ceil(.2 * len(margins)) - 1)], "worst_margin": margins[0],
        "wins_or_ties": sum(r["rank"] == 1 for r in rows),
        "max_runtime_seconds": max(r["runtime_seconds"] for r in rows),
        "invalid_actions": sum(r["invalid_actions"] for r in rows)}


def compare(champion: dict, candidate: dict) -> dict:
    deltas = {key: candidate[key] - champion[key] for key in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")}
    signals = {"rank": deltas["mean_rank"] < 0, "mean_margin": deltas["mean_margin"] > 0,
        "p20_tail": deltas["p20_margin"] > 0, "worst_tail": deltas["worst_margin"] > 0}
    passed = sum(signals.values()) >= 2 and deltas["p20_margin"] >= 0 and deltas["worst_margin"] >= 0
    return {"deltas": deltas, "signals": signals, "signal_count": sum(signals.values()),
        "pessimistic_tail_non_regression": deltas["p20_margin"] >= 0 and deltas["worst_margin"] >= 0,
        "passed": passed}


def action_family(order: list) -> str:
    verb = str(order[0]).upper() if order else "EMPTY"
    if verb in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}:
        return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}:
        return "routing"
    if verb in {"PICKUP", "DROP", "FEED", "FERTILIZE"}:
        return "inventory"
    return "production"


def run(policy, opponents: dict[str, Path], panel: list[dict], candidate_module=None) -> list[dict]:
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [policy, str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        before = dict(candidate_module._V39_POLICY.telemetry) if candidate_module else None
        started = time.perf_counter()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        elapsed = time.perf_counter() - started
        terminal, seat = env.steps[-1], identity["seat"]
        rewards = [state.reward for state in terminal]
        invalid, families = 0, Counter()
        for states in env.steps[1:]:
            action = states[seat].action
            if not isinstance(action, dict):
                invalid += 1
                continue
            orders = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
            families.update(action_family(order) for order in orders if isinstance(order, list) and order)
        telemetry = None
        if candidate_module:
            after = candidate_module._V39_POLICY.telemetry
            telemetry = {key: after[key] - before.get(key, 0) for key in after}
        rows.append({**identity, "reward": rewards[seat], "opponent_reward": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat], "rank": 1 if rewards[seat] >= rewards[1-seat] else 2,
            "statuses": [str(state.status) for state in terminal], "steps": len(env.steps),
            "runtime_seconds": elapsed, "mean_step_seconds": elapsed / max(1, len(env.steps)-1),
            "invalid_actions": invalid, "action_families": dict(families), "history_telemetry": telemetry})
    return rows


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate_manifest(fixture, source)
    report = {"issue": "SOT-2966", "axis": "Kaito v39 sparse history-gate independent whole agent",
        "source": source, "checks": checks, "champion": {"path": "main.py", "sha256": sha256(CHAMPION), "modified": False},
        "default_enabled": False, "kaggle_submission": "NOT_PERFORMED",
        "actual_engine": importlib.metadata.version("kaggle-environments")}
    try:
        if fixture["engine"] != f"kaggle-environments=={report['actual_engine']}" or not all(checks.values()):
            raise ValueError("manifest preflight failed")
        manifest = json.loads((ROOT / fixture["opponent_manifest"]).read_text())
        with tempfile.TemporaryDirectory(prefix="sot2966-") as directory:
            work = Path(directory)
            path, acquisition = acquire(work, source)
            report["acquisition"] = acquisition
            if not all(acquisition[key] for key in ("main_hash_ok", "archive_hash_ok", "manifest_hash_ok", "archive_member_ok", "stdlib_only")):
                raise ValueError("artifact portability preflight failed")
            candidate = load_candidate(path)
            report["router_audit"] = audit_router(candidate, fixture)
            opponent_dir = work / "opponents"; opponent_dir.mkdir()
            opponents = fetch_artifacts(manifest, opponent_dir)
            report["screen"] = {"champion_rows": run(str(CHAMPION), opponents, fixture["screen"]),
                "candidate_rows": run(candidate.agent, opponents, fixture["screen"], candidate)}
            for side in ("champion", "candidate"):
                report["screen"][side] = summarize(report["screen"][side + "_rows"])
            report["screen"]["gate"] = compare(report["screen"]["champion"], report["screen"]["candidate"])
            if report["screen"]["gate"]["passed"]:
                report["confirm"] = {"consumed": True,
                    "champion_rows": run(str(CHAMPION), opponents, fixture["confirm"]),
                    "candidate_rows": run(candidate.agent, opponents, fixture["confirm"], candidate)}
                for side in ("champion", "candidate"):
                    report["confirm"][side] = summarize(report["confirm"][side + "_rows"])
                report["confirm"]["gate"] = compare(report["confirm"]["champion"], report["confirm"]["candidate"])
            else:
                report["confirm"] = {"consumed": False, "skipped": True, "reason": "screen pessimistic-tail promotion gate failed"}
        rows = report["screen"]["champion_rows"] + report["screen"]["candidate_rows"]
        if report["confirm"].get("consumed"):
            rows += report["confirm"]["champion_rows"] + report["confirm"]["candidate_rows"]
        report["runtime_contract"] = "PASS" if all(
            r["statuses"] == ["DONE", "DONE"] and r["steps"] == 720 and r["invalid_actions"] == 0 for r in rows) else "FAIL"
        telemetry = [r["history_telemetry"] for r in report["screen"]["candidate_rows"]]
        candidate_families = Counter()
        champion_families = Counter()
        for row in report["screen"]["candidate_rows"]:
            candidate_families.update(row["action_families"])
        for row in report["screen"]["champion_rows"]:
            champion_families.update(row["action_families"])
        report["history_gate_evidence"] = {"per_episode": telemetry,
            "fired": any((t or {}).get("stage2_familiar", 0) or (t or {}).get("delayed_prefix_mismatches", 0) for t in telemetry),
            "route_override": any((t or {}).get("stage1_overrides", 0) or (t or {}).get("stage2_alt", 0) for t in telemetry),
            "screen_action_families": {"candidate": dict(candidate_families), "champion": dict(champion_families)},
            "action_divergence_measured": dict(candidate_families) != dict(champion_families)}
        promoted = report["screen"]["gate"]["passed"] and report["confirm"].get("consumed") and report["confirm"]["gate"]["passed"]
        report["decision"] = "promoted" if promoted else "rejected"
        report["passed"] = report["runtime_contract"] == "PASS" and all(report["router_audit"][key] for key in
            ("checkpoints_match_manifest", "public_state_only", "private_future_metadata_mutation_invariant", "history_gate_present")) and report["router_audit"]["unknown_state"]["abstained_to_conservative_fallback"] and report["history_gate_evidence"]["fired"] and report["history_gate_evidence"]["action_divergence_measured"]
    except Exception as error:
        report.update({"passed": False, "decision": "inconclusive", "reason": f"{type(error).__name__}: {error}"})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

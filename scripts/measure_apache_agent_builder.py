#!/usr/bin/env python3
"""Audit and evaluate the exact Apache-2.0 Apache Agent Builder clean-room hedge."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import importlib.metadata
import json
import tempfile
import time
from collections import Counter
from math import ceil
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import canonical_sha256, fetch_artifacts
except ModuleNotFoundError:
    from measure_leak_free_cv import canonical_sha256, fetch_artifacts

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/apache-agent-builder/agent.py"
SOURCE = ROOT / "candidates/apache-agent-builder/source.json"
FIXTURE = ROOT / "tests/fixtures/apache_agent_builder.json"
OUTPUT = ROOT / "docs/measurements/SOT-2987/SOT-2987-apache-agent-builder.json"
CHAMPION = ROOT / "main.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(ast.parse(CANDIDATE.read_text()))
               if isinstance(node, ast.Import)} | {
        node.module.split(".")[0] for node in ast.walk(ast.parse(CANDIDATE.read_text()))
        if isinstance(node, ast.ImportFrom) and node.module}
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.7",
        "source_version_hash_license_attribution": all(source.get(key) for key in (
            "source_url", "kernel_id", "kernel_version", "notebook_sha256",
            "output_main_sha256", "output_archive_sha256", "license", "license_sha256")),
        "exact_packaged_hash": sha256(CANDIDATE) == source.get("packaged_agent_sha256"),
        "foundation_hash": sha256(ROOT / source["foundation_path"]) == source.get("foundation_sha256"),
        "vendored_license_hash": sha256(ROOT / "candidates/apache-agent-builder/LICENSE-Apache-2.0.txt") == source.get("license_sha256"),
        "stdlib_only": imports <= {"math", "collections"},
        "default_off_independent": source.get("default_enabled") is False and "barnyard" not in CHAMPION.read_text().lower(),
        "same_seed_both_seats": all({r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "screen_confirm_disjoint": all({r[key] for r in screen}.isdisjoint({r[key] for r in confirm})
            for key in ("lineage", "episode", "seed", "time_index")),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "composite_identities_disjoint": {tuple(r[k] for k in ("opponent", "episode", "seed", "seat", "time_index")) for r in screen}.isdisjoint(
            {tuple(r[k] for k in ("opponent", "episode", "seed", "seat", "time_index")) for r in confirm}),
        "replay_bytes_excluded": "public replay action bytes" in source.get("excluded", []),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def family(order: list) -> str:
    verb = str(order[0]).upper() if order else "EMPTY"
    if verb in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}:
        return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}:
        return "routing"
    if verb in {"PICKUP", "DROP", "FEED", "FERTILIZE"}:
        return "inventory"
    return "production"


def run(policy: Path, opponents: dict[str, Path], panel: list[dict]) -> list[dict]:
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [str(policy), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        started = time.perf_counter()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        elapsed = time.perf_counter() - started
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        seat = identity["seat"]
        counts = Counter()
        for states in env.steps[1:]:
            action = states[seat].action
            if not isinstance(action, dict):
                continue
            orders = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
            counts.update(family(order) for order in orders if isinstance(order, list) and order)
        rows.append({**identity, "reward": rewards[seat], "opponent_reward": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat], "rank": 1 if rewards[seat] >= rewards[1-seat] else 2,
            "statuses": [str(state.status) for state in terminal], "steps": len(env.steps),
            "runtime_seconds": elapsed, "action_families": dict(counts)})
    return rows


def summarize(rows: list[dict]) -> dict:
    margins = sorted(row["margin"] for row in rows)
    return {"episodes": len(rows), "mean_rank": sum(r["rank"] for r in rows) / len(rows),
        "mean_margin": sum(margins) / len(margins), "p20_margin": margins[max(0, ceil(.2*len(margins))-1)],
        "worst_margin": margins[0], "wins_or_ties": sum(r["rank"] == 1 for r in rows)}


def compare(champion: dict, candidate: dict) -> dict:
    deltas = {key: candidate[key] - champion[key]
        for key in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")}
    signals = {
        "rank": deltas["mean_rank"] < 0,
        "mean_margin": deltas["mean_margin"] > 0,
        "p20_tail": deltas["p20_margin"] > 0,
        "worst_tail": deltas["worst_margin"] > 0,
    }
    tails_non_regressing = deltas["p20_margin"] >= 0 and deltas["worst_margin"] >= 0
    passed = sum(signals.values()) >= 2 and tails_non_regressing
    return {"deltas": deltas, "signals": signals, "signal_count": sum(signals.values()),
        "tails_non_regressing": tails_non_regressing, "passed": passed}


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate(fixture, source)
    report = {"issue":"SOT-2987", "axis":"Apache Agent Builder clean-room independent whole-agent",
        "source":source, "checks":checks, "champion":{"path":"main.py","sha256":sha256(CHAMPION),"modified":False},
        "default_enabled":False, "public_score_used_for_promotion":False, "kaggle_submission":"NOT_PERFORMED"}
    report["actual_engine"] = importlib.metadata.version("kaggle-environments")
    spec = importlib.util.spec_from_file_location("apache_agent_builder", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    malformed = module.agent({"step": "invalid", "farms": None})
    report["invalid_observation_contract"] = "PASS" if (
        isinstance(malformed, dict) and set(malformed) == {"farmer", "hands", "market"}
    ) else "FAIL"
    if fixture["engine"] != f"kaggle-environments=={report['actual_engine']}" or not all(checks.values()):
        report.update({"passed":False,"decision":"inconclusive","reason":"preflight failed"})
    else:
        manifest = json.loads((ROOT / fixture["opponent_manifest"]).read_text())
        with tempfile.TemporaryDirectory(prefix="sot2951-") as directory:
            opponents = fetch_artifacts(manifest, Path(directory))
            report["screen"] = {
                "champion_rows": run(CHAMPION, opponents, fixture["screen"]),
                "candidate_rows": run(CANDIDATE, opponents, fixture["screen"]),
            }
            for side in ("champion", "candidate"):
                report["screen"][side] = summarize(report["screen"][side + "_rows"])
            report["screen"]["gate"] = compare(report["screen"]["champion"], report["screen"]["candidate"])
            if report["screen"]["gate"]["passed"]:
                report["confirm"] = {
                    "champion_rows": run(CHAMPION, opponents, fixture["confirm"]),
                    "candidate_rows": run(CANDIDATE, opponents, fixture["confirm"]),
                }
                for side in ("champion", "candidate"):
                    report["confirm"][side] = summarize(report["confirm"][side + "_rows"])
                report["confirm"]["gate"] = compare(report["confirm"]["champion"], report["confirm"]["candidate"])
            else:
                report["confirm"] = {"skipped": True, "reason": "screen promotion gate failed"}
        candidate_rows = report["screen"]["candidate_rows"]
        champion_rows = report["screen"]["champion_rows"]
        candidate_fingerprint = Counter(f for r in candidate_rows for f,n in r["action_families"].items() for _ in range(n))
        champion_fingerprint = Counter(f for r in champion_rows for f,n in r["action_families"].items() for _ in range(n))
        fingerprints = {"candidate_screen":dict(candidate_fingerprint),"champion_screen":dict(champion_fingerprint)}
        report["action_family_fingerprint"] = {"counts":fingerprints,"sha256":canonical_sha256(fingerprints),
            "diverged_from_champion":dict(candidate_fingerprint) != dict(champion_fingerprint)}
        evaluated_rows = list(report["screen"]["champion_rows"] + report["screen"]["candidate_rows"])
        if not report["confirm"].get("skipped"):
            evaluated_rows += report["confirm"]["champion_rows"] + report["confirm"]["candidate_rows"]
        contract = all(r["statuses"] == ["DONE","DONE"] and r["steps"] == 720
            and r["runtime_seconds"] < fixture["episode_timeout_seconds"] for r in evaluated_rows)
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        promoted = report["screen"]["gate"]["passed"] and not report["confirm"].get("skipped") and report["confirm"]["gate"]["passed"]
        report["decision"] = "promoted-independent-hedge" if promoted else "rejected-candidate-inactive"
        report["passed"] = (contract and report["invalid_observation_contract"] == "PASS"
            and report["action_family_fingerprint"]["diverged_from_champion"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"passed":report["passed"],"decision":report["decision"],"output":str(OUTPUT)},sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

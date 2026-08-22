#!/usr/bin/env python3
"""Evaluate the clean-room reactive optimal-task whole-agent lineage."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
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
CANDIDATE = ROOT / "candidates/reactive-optimal-task/agent.py"
SOURCE = ROOT / "candidates/reactive-optimal-task/source.json"
FIXTURE = ROOT / "tests/fixtures/reactive_optimal_task.json"
OUTPUT = ROOT / "docs/measurements/SOT-2989/SOT-2989-reactive-optimal-task.json"
CHAMPION = ROOT / "main.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    tree = ast.parse(CANDIDATE.read_text())
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
    imports |= {node.module.split(".")[0] for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module}
    split_keys = ("opponent", "episode", "seed", "time_index")
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.7",
        "source_version_license_hash_boundary": all(source.get(key) for key in (
            "source_url", "kernel_id", "kernel_version", "notebook_sha256",
            "kernel_metadata_sha256", "output_main_sha256", "license", "license_boundary")),
        "candidate_hash_pinned": sha256(CANDIDATE) == source.get("candidate_sha256"),
        "clean_room_unlicensed_boundary": source.get("license") == "UNDECLARED"
            and "notebook source code" in source.get("excluded", []),
        "stdlib_only": imports <= {"collections"},
        "default_off_independent": source.get("default_enabled") is False
            and "reactive-optimal-task" not in CHAMPION.read_text(),
        "same_seed_both_seats": all(
            {row["seat"] for row in panel if row["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {row["seed"] for row in panel}),
        "opponent_episode_seed_time_disjoint": all(
            {row[key] for row in screen}.isdisjoint({row[key] for row in confirm})
            for key in split_keys),
        "composite_identities_disjoint": {
            tuple(row[key] for key in (*split_keys, "seat")) for row in screen
        }.isdisjoint({tuple(row[key] for key in (*split_keys, "seat")) for row in confirm}),
        "chronological_confirm": max(row["time_index"] for row in screen)
            < min(row["time_index"] for row in confirm),
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


def load_candidate():
    spec = importlib.util.spec_from_file_location("reactive_optimal_task", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(policy, opponents: dict[str, Path], panel: list[dict]) -> list[dict]:
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [policy, str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        started = time.perf_counter()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        elapsed = time.perf_counter() - started
        terminal = env.steps[-1]
        rewards = [state.reward or 0 for state in terminal]
        seat = identity["seat"]
        counts, invalid = Counter(), 0
        for states in env.steps[1:]:
            action = states[seat].action
            if not isinstance(action, dict) or set(action) != {"farmer", "hands", "market"}:
                invalid += 1
                continue
            orders = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
            for order in orders:
                if not isinstance(order, list) or not order:
                    invalid += 1
                else:
                    counts[family(order)] += 1
        rows.append({**identity, "reward": rewards[seat], "opponent_reward": rewards[1-seat],
                     "margin": rewards[seat] - rewards[1-seat],
                     "rank": 1 if rewards[seat] >= rewards[1-seat] else 2,
                     "statuses": [str(state.status) for state in terminal], "steps": len(env.steps),
                     "runtime_seconds": elapsed, "invalid_actions": invalid,
                     "action_families": dict(counts)})
    return rows


def summarize(rows: list[dict]) -> dict:
    margins = sorted(row["margin"] for row in rows)
    return {"episodes": len(rows), "mean_rank": sum(row["rank"] for row in rows) / len(rows),
            "mean_margin": sum(margins) / len(margins),
            "p20_margin": margins[max(0, ceil(0.2 * len(margins)) - 1)],
            "worst_margin": margins[0], "wins_or_ties": sum(row["rank"] == 1 for row in rows)}


def compare(champion: dict, candidate: dict) -> dict:
    deltas = {key: candidate[key] - champion[key]
              for key in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")}
    signals = {"rank": deltas["mean_rank"] < 0, "mean_margin": deltas["mean_margin"] > 0,
               "p20_tail": deltas["p20_margin"] > 0, "worst_tail": deltas["worst_margin"] > 0}
    passed = sum(signals.values()) >= 2 and deltas["p20_margin"] >= 0 and deltas["worst_margin"] >= 0
    return {"deltas": deltas, "signals": signals, "signal_count": sum(signals.values()), "passed": passed}


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate(fixture, source)
    module = load_candidate()
    malformed = module.agent({"step": "invalid", "farms": None})
    invalid_contract = isinstance(malformed, dict) and set(malformed) == {"farmer", "hands", "market"}
    report = {"issue": "SOT-2989", "axis": "reactive optimal-task clean-room independent whole-agent",
              "source": source, "checks": checks,
              "champion": {"path": "main.py", "sha256": sha256(CHAMPION), "modified": False},
              "candidate": {"path": str(CANDIDATE.relative_to(ROOT)), "sha256": sha256(CANDIDATE)},
              "default_enabled": False, "public_score_used_for_promotion": False,
              "invalid_observation_contract": "PASS" if invalid_contract else "FAIL",
              "kaggle_submission": "NOT_PERFORMED",
              "actual_engine": importlib.metadata.version("kaggle-environments")}
    if fixture["engine"] != f"kaggle-environments=={report['actual_engine']}" or not all(checks.values()):
        report.update({"passed": False, "decision": "inconclusive", "reason": "preflight failed"})
    else:
        manifest = json.loads((ROOT / fixture["opponent_manifest"]).read_text())
        with tempfile.TemporaryDirectory(prefix="sot2989-") as directory:
            opponents = fetch_artifacts(manifest, Path(directory))
            for window in ("screen", "confirm"):
                champion_rows = run(str(CHAMPION), opponents, fixture[window])
                candidate_rows = run(module.agent, opponents, fixture[window])
                report[window] = {"champion_rows": champion_rows, "candidate_rows": candidate_rows,
                                  "champion": summarize(champion_rows), "candidate": summarize(candidate_rows)}
                report[window]["gate"] = compare(report[window]["champion"], report[window]["candidate"])
        trace = module.trace_snapshot()
        report["task_selection_intervention_log"] = trace
        fingerprints = {window: {
            side: dict(Counter(family_name for row in report[window][side + "_rows"]
                               for family_name, count in row["action_families"].items()
                               for _ in range(count))) for side in ("champion", "candidate")
        } for window in ("screen", "confirm")}
        report["action_family_fingerprint"] = {"counts": fingerprints,
                                                "sha256": canonical_sha256(fingerprints),
                                                "diverged_from_champion": any(
                                                    fingerprints[w]["candidate"] != fingerprints[w]["champion"]
                                                    for w in ("screen", "confirm"))}
        rows = [row for window in ("screen", "confirm") for side in ("champion", "candidate")
                for row in report[window][side + "_rows"]]
        contract = all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720
                       and row["runtime_seconds"] < fixture["episode_timeout_seconds"]
                       and row["invalid_actions"] == 0 for row in rows)
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        promoted = report["screen"]["gate"]["passed"] and report["confirm"]["gate"]["passed"]
        fired = trace["calls"] > 0 and sum(trace["assigned"].values()) > 0
        report["decision"] = "promoted-independent-hedge" if promoted else (
            "rejected-candidate-inactive" if fired else "inconclusive")
        report["passed"] = contract and invalid_contract and fired and report["action_family_fingerprint"]["diverged_from_champion"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

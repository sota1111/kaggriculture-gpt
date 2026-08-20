#!/usr/bin/env python3
"""Direct same-seed/both-seat screen A/B for the feed-economic flag."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from scripts.measure_shop_prefix_closed_loop import _gate, _summary, _run
    from scripts.measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest
except ModuleNotFoundError:
    from measure_shop_prefix_closed_loop import _gate, _summary, _run
    from measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def targeted_trace(policy_path: Path) -> dict:
    policy = _load(policy_path, "sot2833_targeted")
    policy.FEED_ECONOMIC_DECISION = True
    rows = []
    for seat in (0, 1):
        farm = {"money": 2400, "farmer": [0, 0], "hands": [], "tiles": [[None]],
                "daily_operating_cost": 100}
        obs = {"player": seat, "day": 8, "total_days": 30,
               "farms": [dict(farm), dict(farm)],
               "private": {"animals": {"COW": 2, "SHEEP": 1},
                           "shed": {"WHEAT": 1}, "inventories": [{"WHEAT": 0}]},
               "market": {"prices": {"WHEAT": 25}},
               "town": {"unlocked_shops": ["YARN_STORE"]},
               "capabilities": ["BUY_PRODUCT"]}
        decision = policy._feed_economic_order(obs)
        mutated = json.loads(json.dumps(obs))
        mutated.update({"episode_id": "hidden", "submission_id": "hidden", "seed": 999})
        rows.append({"seat": seat, "order": decision,
                     "identity_seed_invariant": decision == policy._feed_economic_order(mutated)})
    return {"rows": rows, "both_seats": {row["seat"] for row in rows} == {0, 1},
            "actual_intervention": all(row["order"] and row["order"][0][:2]
                                       == ["BUY_PRODUCT", "WHEAT"] for row in rows),
            "firings": policy.component_firing_counts()["feed_economic"]}


def _run_candidate(policy_path: Path, opponent: Path, row: dict, seat: int) -> dict:
    from kaggle_environments import make
    policy = _load(policy_path, f"sot2833_candidate_{row['seed']}_{seat}_{time.perf_counter_ns()}")
    policy.FEED_ECONOMIC_DECISION = True
    agents = [policy.agent, str(opponent)]
    if seat == 1:
        agents.reverse()
    stdout, stderr = io.StringIO(), io.StringIO()
    env = make("kaggriculture", configuration={"seed": row["seed"]}, debug=True)
    started = time.perf_counter()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        steps = env.run(agents)
    elapsed = time.perf_counter() - started
    rewards = [float(agent.reward) for agent in env.state]
    own, other = rewards[seat], rewards[1 - seat]
    return {"reward": own, "opponent_reward": other, "margin": own - other,
            "rank": 1 if own >= other else 2, "seconds": elapsed, "states": len(steps),
            "statuses": [agent.status for agent in env.state],
            "invalid_actions": sum(len(agent.info.get("errors", [])) for agent in env.state),
            "contract_violations": sum(len(agent.info.get("log", [])) for agent in env.state
                                       if agent.status != "DONE"), "stderr": stderr.getvalue(),
            "feed_economic_firings": policy.component_firing_counts()["feed_economic"]}


def _window(policy_path: Path, artifacts: dict, identities: list, window: str) -> dict:
    rows = []
    for identity in identities:
        for seat in (0, 1):
            champion = _run(policy_path, artifacts[identity["opponent"]], identity, seat, False)
            candidate = _run_candidate(policy_path, artifacts[identity["opponent"]], identity, seat)
            rows.append({"identity": {"window": window, "opponent": identity["opponent"],
                                      "seed": identity["seed"], "time_utc": identity["time_utc"],
                                      "candidate_seat": seat},
                         "champion": champion, "candidate": candidate,
                         "candidate_delta": {"reward": candidate["reward"] - champion["reward"],
                                             "margin": candidate["margin"] - champion["margin"]}})
    result = {"summary": _summary(rows), "raw_rows": rows}
    passed, reasons = _gate(result, True)
    result.update({"passed": passed, "reasons": reasons})
    return result


def measure(policy_path: Path, manifest: dict) -> dict:
    checks, trace = validate_manifest(manifest), targeted_trace(policy_path)
    if not all(checks.values()) or not trace["both_seats"] or not trace["actual_intervention"]:
        return {"issue": "SOT-2833", "decision": "inconclusive", "passed": False,
                "manifest_checks": checks, "targeted_trace": trace,
                "confirm": {"skipped": True, "reason": "pre-screen checks failed"},
                "kaggle_submission": "NOT_PERFORMED"}
    with tempfile.TemporaryDirectory(prefix="sot2833-public-agents-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        screen = _window(policy_path, artifacts, manifest["panels"]["screen"], "screen")
        if screen["passed"]:
            confirm = _window(policy_path, artifacts, manifest["panels"]["confirm"], "confirm")
        else:
            confirm = {"skipped": True, "reason": "screen gate failed; confirm not consumed"}
    promoted = screen["passed"] and not confirm.get("skipped") and confirm["passed"]
    return {"issue": "SOT-2833", "axis": "winner-derived public-state feed-wheat runway",
            "source": {"url": "https://github.com/zansued/kaggriculture-ai-agent",
                       "commit": "9de2779147c004ab9e7b1545cd62ace4ef7ad1cd", "license": "MIT"},
            "selected_family": "economic", "manifest_checks": checks,
            "targeted_trace": trace, "screen": screen, "confirm": confirm,
            "runtime_candidate_retained": promoted,
            "effective_config": {"FEED_ECONOMIC_DECISION": promoted},
            "candidate_artifact": {"path": "main.py", "sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest()},
            "decision": "promoted" if promoted else "rejected", "passed": promoted,
            "kaggle_submission": "NOT_PERFORMED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_closed_loop_holdout.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2831/SOT-2833-feed-economic-decision.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()))
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"],
                      "screen_passed": report.get("screen", {}).get("passed"),
                      "confirm_skipped": report["confirm"].get("skipped", False)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

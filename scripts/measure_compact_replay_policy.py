#!/usr/bin/env python3
"""Direct screen A/B for the independently flagged compact replay policy."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
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
    policy = _load(policy_path, "sot2826_targeted")
    policy.COMPACT_REPLAY_POLICY = True
    rows = []
    for day, hour, unlocked, hands in ((0, 0, 1, 0), (5, 2, 1, 4), (8, 8, 2, 8), (9, 0, 3, 11)):
        observation = {"player": 0, "day": day, "hour": hour,
                       "farms": [{"unlocked_quadrants": [str(i) for i in range(unlocked)],
                                  "hands": [[0, 0]] * hands}]}
        decision = policy._compact_replay_production(observation, 4, record=True)
        rows.append({"state": [day, hour, unlocked, hands], "decision": decision})
    return {"rows": rows, "firings": policy.component_firing_counts()["compact_replay_policy"],
            "all_branches_fired": all(policy.component_firing_counts()["compact_replay_policy"].values())}


def measure(policy_path: Path, manifest: dict) -> dict:
    checks = validate_manifest(manifest)
    trace = targeted_trace(policy_path)
    if not all(checks.values()) or not trace["all_branches_fired"]:
        return {"issue": "SOT-2826", "decision": "inconclusive", "passed": False,
                "manifest_checks": checks, "targeted_trace": trace,
                "kaggle_submission": "NOT_PERFORMED"}
    with tempfile.TemporaryDirectory(prefix="sot2826-public-agents-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        raw = []
        for identity in manifest["panels"]["screen"]:
            for seat in (0, 1):
                champion = _run(policy_path, artifacts[identity["opponent"]], identity, seat, False)
                # _run controls the older selector; load a small wrapper policy path by
                # temporarily replacing the compact flag in the generic runner below.
                candidate = _run_compact(policy_path, artifacts[identity["opponent"]], identity, seat)
                raw.append({"identity": {"window": "screen", "opponent": identity["opponent"],
                                         "seed": identity["seed"], "time_utc": identity["time_utc"],
                                         "candidate_seat": seat},
                            "champion": champion, "candidate": candidate,
                            "candidate_delta": {"reward": candidate["reward"] - champion["reward"],
                                                "margin": candidate["margin"] - champion["margin"]}})
        screen = {"summary": _summary(raw), "raw_rows": raw}
        passed, reasons = _gate(screen, True)
        screen.update({"passed": passed, "reasons": reasons})
    return {"issue": "SOT-2826", "axis": "screen-distilled state-conditioned production cadence",
            "teacher_dataset_sha256": policy_constants(policy_path)["teacher_dataset_sha256"],
            "manifest_checks": checks, "targeted_trace": trace, "screen": screen,
            "confirm": {"skipped": True, "reason": "child contract: screen-only tuning and gate"},
            "effective_config": {"COMPACT_REPLAY_POLICY": passed},
            "runtime_candidate_retained": passed, "decision": "promoted" if passed else "rejected",
            "passed": passed, "candidate_artifact": {"path": "main.py",
                "sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest()},
            "kaggle_submission": "NOT_PERFORMED"}


def policy_constants(path: Path) -> dict:
    return _load(path, "sot2826_constants").COMPACT_REPLAY_POLICY_CONSTANTS


def _run_compact(policy_path: Path, opponent: Path, row: dict, seat: int) -> dict:
    import contextlib
    import io
    import time
    from kaggle_environments import make

    policy = _load(policy_path, f"sot2826_candidate_{row['seed']}_{seat}_{time.perf_counter_ns()}")
    policy.COMPACT_REPLAY_POLICY = True
    agents = [policy.agent, str(opponent)]
    if seat == 1:
        agents.reverse()
    stdout, stderr = io.StringIO(), io.StringIO()
    environment = make("kaggriculture", configuration={"seed": row["seed"]}, debug=True)
    started = time.perf_counter()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        steps = environment.run(agents)
    elapsed = time.perf_counter() - started
    rewards = [float(agent.reward) for agent in environment.state]
    own, other = rewards[seat], rewards[1 - seat]
    return {"reward": own, "opponent_reward": other, "margin": own - other,
            "rank": 1 if own >= other else 2, "seconds": elapsed, "states": len(steps),
            "statuses": [agent.status for agent in environment.state],
            "invalid_actions": sum(len(agent.info.get("errors", [])) for agent in environment.state),
            "contract_violations": sum(len(agent.info.get("log", [])) for agent in environment.state
                                       if agent.status != "DONE"), "stderr": stderr.getvalue(),
            "compact_firings": policy.component_firing_counts()["compact_replay_policy"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_closed_loop_holdout.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2823/SOT-2826-compact-replay-policy.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()))
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "screen_passed": report.get("screen", {}).get("passed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

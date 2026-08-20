#!/usr/bin/env python3
"""Isolated same-seed/both-seat gate for the sequence precursor policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    from scripts.measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest
    from scripts.measure_shop_prefix_closed_loop import _gate, _run, _summary
except ModuleNotFoundError:
    from measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest
    from measure_shop_prefix_closed_loop import _gate, _run, _summary


def targeted_trace(policy_path: Path) -> dict:
    """Exercise task -> location -> economic action without identity inputs."""
    import importlib.util

    def load(name: str):
        spec = importlib.util.spec_from_file_location(name, policy_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        module.PUBLIC_SHOP_PREFIX_ROUTE_SELECTOR = False
        return module

    rows = []
    for seat in (0, 1):
        policy = load(f"sot2837_trace_{seat}")
        policy.SEQUENCE_PRECURSOR_POLICY = True
        tiles = [["LOCKED" for _ in range(3)] for _ in range(3)]
        tiles[1][1] = {"kind": "PASTURE"}
        tiles[1][2] = None
        farm = {"money": 750, "farmer": [2, 1], "hands": [], "tiles": tiles}
        obs = {"player": seat, "step": 1, "day": 0, "hour": 1, "turns_per_day": 24,
               "total_days": 30, "farms": [json.loads(json.dumps(farm)), json.loads(json.dumps(farm))],
               "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
               "market": {"prices": {}, "inventory": {}} , "town": {"unlocked_shops": []}}
        action = policy.agent(obs)
        counts = policy.component_firing_counts()["sequence_precursor_policy"]
        mutated = json.loads(json.dumps(obs))
        mutated.update({"episode_id": "hidden", "submission_id": "hidden", "seed": 999999})
        other = load(f"sot2837_invariant_{seat}")
        other.SEQUENCE_PRECURSOR_POLICY = True
        invariant = other.agent(mutated)
        rows.append({"seat": seat, "action": action["farmer"], "phase": counts["phase"],
                     "firings": counts["firings"], "economic_reached": counts["economic_reached"],
                     "identity_seed_invariant": action == invariant})
    return {"rows": rows, "both_seats": {row["seat"] for row in rows} == {0, 1},
            "actual_intervention": all(row["action"] == ["BUILD_PASTURE"] for row in rows),
            "precursor_economic_reached": all(row["economic_reached"] == 1 for row in rows),
            "identity_seed_invariant": all(row["identity_seed_invariant"] for row in rows)}


def _run_window(policy_path: Path, artifacts: dict, identities: list, window: str) -> dict:
    rows = []
    for identity in identities:
        for seat in (0, 1):
            champion = _run(policy_path, artifacts[identity["opponent"]], identity, seat, False)
            candidate = _run_precursor(policy_path, artifacts[identity["opponent"]], identity, seat)
            rows.append({"identity": {"window": window, "opponent": identity["opponent"],
                                      "seed": identity["seed"], "time_utc": identity["time_utc"],
                                      "candidate_seat": seat},
                         "champion": champion, "candidate": candidate,
                         "candidate_delta": {"reward": candidate["reward"] - champion["reward"],
                                             "margin": candidate["margin"] - champion["margin"]}})
    result = {"summary": _summary(rows), "raw_rows": rows}
    passed, reasons = _gate(result, True)
    if not any(row["candidate"]["precursor"]["firings"] > 0 and
               row["candidate"]["precursor"]["economic_reached"] > 0 for row in rows):
        passed = False
        reasons.append("component did not fire and reach BUILD_PASTURE in the paired panel")
    result.update({"passed": passed, "reasons": reasons})
    return result


def _run_precursor(policy_path: Path, opponent: Path, row: dict, seat: int) -> dict:
    import contextlib
    import importlib.util
    import io
    from kaggle_environments import make

    spec = importlib.util.spec_from_file_location(f"sot2837_{row['seed']}_{seat}_{time.perf_counter_ns()}", policy_path)
    policy = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(policy)
    policy.SEQUENCE_PRECURSOR_POLICY = True
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
            "contract_violations": sum(len(agent.info.get("log", [])) for agent in env.state if agent.status != "DONE"),
            "stderr": stderr.getvalue(),
            "precursor": policy.component_firing_counts()["sequence_precursor_policy"]}


def measure(policy_path: Path, manifest: dict, fixture: dict) -> dict:
    checks, trace = validate_manifest(manifest), targeted_trace(policy_path)
    fixture_checks = {"same_seed_panels": fixture["screen_seeds"] == [row["seed"] for row in manifest["panels"]["screen"]]
                      and fixture["confirm_seeds"] == [row["seed"] for row in manifest["panels"]["confirm"]],
                      "both_seats": fixture["seats"] == [0, 1],
                      "no_submission": fixture["kaggle_submission"] == "NOT_PERFORMED"}
    if not all(checks.values()) or not all(fixture_checks.values()) or not all(
            trace[key] for key in ("both_seats", "actual_intervention", "precursor_economic_reached", "identity_seed_invariant")):
        return {"issue": "SOT-2837", "decision": "inconclusive", "passed": False,
                "manifest_checks": checks, "fixture_checks": fixture_checks, "targeted_trace": trace,
                "confirm": {"skipped": True, "reason": "pre-screen checks failed"},
                "effective_config": {"SEQUENCE_PRECURSOR_POLICY": False}, "kaggle_submission": "NOT_PERFORMED"}
    import tempfile
    with tempfile.TemporaryDirectory(prefix="sot2837-public-agents-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        screen = _run_window(policy_path, artifacts, manifest["panels"]["screen"], "screen")
        confirm = (_run_window(policy_path, artifacts, manifest["panels"]["confirm"], "confirm")
                   if screen["passed"] else {"skipped": True, "reason": "screen gate failed; confirm not consumed"})
    promoted = screen["passed"] and not confirm.get("skipped") and confirm["passed"]
    return {"issue": "SOT-2837", "axis": "sequence-conditioned early pasture precursor",
            "source_evidence": "docs/measurements/SOT-2835/SOT-2836-winner-sequence-support.json",
            "manifest_checks": checks, "fixture_checks": fixture_checks, "targeted_trace": trace,
            "screen": screen, "confirm": confirm, "decision": "promoted" if promoted else "rejected",
            "passed": promoted, "runtime_candidate_retained": promoted,
            "effective_config": {"SEQUENCE_PRECURSOR_POLICY": promoted},
            "candidate_artifact": {"path": "main.py", "sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest()},
            "kaggle_submission": "NOT_PERFORMED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_closed_loop_holdout.json"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/sequence_precursor_panel.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2835/SOT-2837-sequence-precursor-policy.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()), json.loads(args.fixture.read_text()))
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "screen_passed": report.get("screen", {}).get("passed"),
                      "confirm_skipped": report["confirm"].get("skipped", False)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

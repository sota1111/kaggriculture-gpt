#!/usr/bin/env python3
"""Seal the capacity-aware dispatcher promotion decision (SOT-2853)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    from scripts.evaluate import validate_cv_holdouts
    from scripts.measure_capacity_dispatcher import measure as measure_dispatcher
except ModuleNotFoundError:
    from evaluate import validate_cv_holdouts
    from measure_capacity_dispatcher import measure as measure_dispatcher


def _sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _primary_metrics(screen: dict) -> dict:
    paired = screen["direct_ab"]
    episodes = paired["episodes"]
    reward_deltas = sorted(float(row["reward_delta"]) for row in episodes)
    rank_deltas = [float(row["champion_rank"] - row["candidate_rank"]) for row in episodes]
    # The opponent, seed, and seat are identical within each pair, so own-reward
    # delta is also the paired margin delta.
    return {
        "mean_rank_improvement": sum(rank_deltas) / len(rank_deltas),
        "mean_margin_delta": sum(reward_deltas) / len(reward_deltas),
        "lower_tail_margin_delta": reward_deltas[max(0, len(reward_deltas) // 4 - 1)],
        "worst_margin_delta": reward_deltas[0],
        "candidate_wins_or_ties": paired["summary"]["candidate_wins_or_ties"],
    }


def measure(policy: Path, fixture: dict, oracle: dict) -> dict:
    isolation = validate_cv_holdouts(fixture["leak_free_cv"])
    oracle_ok = bool(oracle.get("passed")) and oracle.get("result") == "promoted"
    first = measure_dispatcher(policy, fixture)
    second = measure_dispatcher(policy, fixture)
    deterministic = _sha(first) == _sha(second)
    screen = dict(first["screen"])
    screen["primary"] = _primary_metrics(screen)
    screen["passed"] = not screen["gate_reasons"]
    confirm = first["confirm"]
    confirm_was_gated = (screen["passed"] and not confirm.get("skipped", False)) or (
        not screen["passed"] and confirm.get("skipped", False)
    )
    evidence_valid = first["targeted_firing_trace"]["firings_delta"] > 0
    if not all(isolation.values()) or not oracle_ok or not deterministic or not confirm_was_gated:
        decision = "inconclusive"
    elif screen["passed"] and not confirm.get("gate_reasons"):
        decision = "promoted"
    elif evidence_valid:
        decision = "rejected"
    else:
        decision = "inconclusive"
    promoted = decision == "promoted"
    return {
        "issue": "SOT-2853",
        "axis": "capacity-aware dispatcher sealed promotion panel",
        "decision": decision,
        "passed": decision in {"promoted", "rejected"},
        "screen": screen,
        "confirm": confirm,
        "screen_pass_only_confirm": confirm_was_gated,
        "sealed_holdout_checks": isolation,
        "oracle": {
            "issue": oracle.get("issue"), "result": oracle.get("result"),
            "passed": oracle_ok, "sha256": _sha(oracle),
        },
        "deterministic_rerun": {"passed": deterministic, "sha256": _sha(first)},
        "intervention_evidence": first["targeted_firing_trace"],
        "secondary": {
            "baseline": screen["baseline_actions"], "candidate": screen["candidate_actions"],
            "productive_density_delta": screen["candidate_actions"]["productive_density"] - screen["baseline_actions"]["productive_density"],
            "travel_delta": screen["candidate_actions"]["travel"] - screen["baseline_actions"]["travel"],
            "repair_delta": screen["candidate_actions"]["intervention"]["budget_repairs"] - screen["baseline_actions"]["intervention"]["budget_repairs"],
        },
        "gate_reasons": first["gate_reasons"],
        "effective_config": {"CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER": promoted},
        "candidate_artifact": {
            "path": "main.py", "sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
            "retained": promoted,
        },
        "information_boundary": first["information_boundary"],
        "submission_contract": "PENDING",
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--oracle", type=Path, default=Path("docs/measurements/SOT-2850/SOT-2851-public-action-capacity-oracle.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2850/SOT-2853-capacity-dispatcher-sealed-panel.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.fixture.read_text()), json.loads(args.oracle.read_text()))
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")), str(args.policy.resolve())], capture_output=True, text=True)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["passed"] = bool(report["passed"]) and contract.returncode == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"], "screen_passed": report["screen"]["passed"], "confirm_skipped": report["confirm"].get("skipped", False)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

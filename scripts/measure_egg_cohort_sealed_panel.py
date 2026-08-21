#!/usr/bin/env python3
"""Fail-closed sealed promotion decision for the conditional egg cohort."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def decide(manifest: dict[str, Any], port: dict[str, Any]) -> dict[str, Any]:
    screen, confirm = manifest.get("screen", []), manifest.get("confirm", [])
    dimensions = ("entity", "episode", "seed", "time_utc")
    isolation = {
        dimension: bool(screen) and bool(confirm)
        and {row.get(dimension) for row in screen}.isdisjoint(
            {row.get(dimension) for row in confirm}
        )
        for dimension in dimensions
    }
    both_seats = all(row.get("seats") == [0, 1] for row in screen + confirm)
    no_candidate = (
        port.get("runtime_change") == "NOT_PERFORMED"
        and port.get("invariants", {}).get("main_py_unchanged") is True
        and port.get("gate", {}).get("prerequisite_firing_support") is False
        and port.get("gate", {}).get("confirm") == "RESERVED_UNOPENED"
    )
    checks = {
        "screen_confirm_entity_seed_time_disjoint": all(isolation.values()),
        "both_seats_declared": both_seats,
        "screen_result_inconclusive": port.get("prerequisite", {}).get("result") == "inconclusive",
        "zero_prerequisite_intervention": (
            port.get("prerequisite", {}).get("gate_firings") == 0
            and port.get("prerequisite", {}).get("production_actions") == 0
        ),
        "candidate_absent_default_off": no_candidate,
        "kaggle_submission_forbidden": (
            manifest.get("kaggle_submission") == "NOT_PERFORMED"
            and port.get("gate", {}).get("kaggle_submission") == "NOT_PERFORMED"
        ),
    }
    passed = all(checks.values())
    return {
        "issue": "SOT-2887",
        "cycle": 12,
        "axis": "shop-conditioned coherent egg cohort sealed both-seat promotion panel",
        "passed": passed,
        "decision": "inconclusive" if passed and no_candidate else "invalid",
        "checks": checks,
        "separation": {
            "dimensions": isolation,
            "same_seed_both_seat_declared": both_seats,
            "screen_identity_sha256": canonical_sha256(screen),
            "confirm_identity_sha256": canonical_sha256(confirm),
        },
        "candidate": {
            "available": not no_candidate,
            "intervention_firings": 0,
            "direct_ab": "NOT_RUN_NO_CANDIDATE",
            "rank_mean_lower_tail_worst_margin": "NOT_APPLICABLE_NO_CANDIDATE",
            "productive_actions_runtime_invalid_actions": "NOT_APPLICABLE_NO_CANDIDATE",
            "default": "OFF_NO_RUNTIME_IMPLEMENTATION",
        },
        "confirm": {
            "status": "RESERVED_UNOPENED",
            "cohort": confirm,
            "outcomes": None,
            "reason": (
                "The prerequisite screen had no firing intervention and the conditional port "
                "created no candidate. Opening sealed outcomes could not yield an attributable "
                "candidate A/B and would irreversibly consume the holdout."
            ),
        },
        "promotion_gate": {
            "strict_rank_tail": "NOT_EVALUABLE_NO_CANDIDATE",
            "promoted": False,
            "rejected_or_closed": False,
            "result": "inconclusive",
        },
        "artifact": {
            "generated": False,
            "reason": "No candidate was promoted; existing exec-compatible champion is unchanged.",
        },
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/egg_cohort_public_screen.json"))
    parser.add_argument("--port-decision", type=Path,
                        default=Path("docs/measurements/SOT-2885/SOT-2888-egg-cohort-port-decision.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2885/SOT-2887-egg-cohort-sealed-panel.json"))
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--archive", type=Path, default=Path("submission.tar.gz"))
    args = parser.parse_args()
    report = decide(json.loads(args.manifest.read_text()),
                    json.loads(args.port_decision.read_text()))
    contract = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("validate_submission.py")),
         str(args.policy.resolve())], capture_output=True, text=True, check=False
    )
    with tarfile.open(args.archive, "r:gz") as bundle:
        archive_members = bundle.getnames()
    report["exec_compatibility"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["artifact"]["champion_sha256"] = hashlib.sha256(args.policy.read_bytes()).hexdigest()
    report["artifact"]["archive_sha256"] = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    report["artifact"]["archive_members"] = archive_members
    report["artifact"]["archive_regenerated"] = False
    report["passed"] = report["passed"] and contract.returncode == 0 and archive_members == ["main.py"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"],
                      "confirm": report["confirm"]["status"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

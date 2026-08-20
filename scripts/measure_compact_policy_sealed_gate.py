#!/usr/bin/env python3
"""Gate the distilled compact policy on the unseen sealed closed-loop panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from scripts.measure_compact_replay_policy import (
        _run_compact,
        policy_constants,
        targeted_trace,
    )
    from scripts.measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest
    from scripts.measure_shop_prefix_closed_loop import _gate, _run, _summary
except ModuleNotFoundError:
    from measure_compact_replay_policy import _run_compact, policy_constants, targeted_trace
    from measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest
    from measure_shop_prefix_closed_loop import _gate, _run, _summary


def _window(policy_path: Path, artifacts: dict[str, Path], rows: list[dict]) -> dict:
    raw = []
    for identity in rows:
        for seat in (0, 1):
            champion = _run(policy_path, artifacts[identity["opponent"]], identity, seat, False)
            candidate = _run_compact(policy_path, artifacts[identity["opponent"]], identity, seat)
            raw.append({
                "identity": {
                    "window": "sealed-screen",
                    "source_window": "confirm",
                    "opponent": identity["opponent"],
                    "seed": identity["seed"],
                    "time_utc": identity["time_utc"],
                    "candidate_seat": seat,
                },
                "champion": champion,
                "candidate": candidate,
                "candidate_delta": {
                    "reward": candidate["reward"] - champion["reward"],
                    "margin": candidate["margin"] - champion["margin"],
                },
            })
    return {"summary": _summary(raw), "raw_rows": raw}


def _sealed_gate(window: dict) -> tuple[bool, list[str]]:
    passed, reasons = _gate(window, True)
    champion_mean_rank = sum(
        row["champion"]["rank"] for row in window["raw_rows"]
    ) / len(window["raw_rows"])
    window["summary"]["champion_mean_rank"] = champion_mean_rank
    if window["summary"]["candidate_mean_rank"] > champion_mean_rank:
        reasons.append("mean rank regressed")
    if window["summary"]["mean_reward_delta"] < 0:
        reasons.append("mean reward regressed")
    return not reasons, reasons


def measure(policy_path: Path, manifest: dict) -> dict:
    checks = validate_manifest(manifest)
    trace = targeted_trace(policy_path)
    if not all(checks.values()) or not trace["all_branches_fired"]:
        return {
            "issue": "SOT-2825", "decision": "inconclusive", "passed": False,
            "manifest_checks": checks, "targeted_trace": trace,
            "kaggle_submission": "NOT_PERFORMED",
        }

    # SOT-2826 tuned and screened only on the manifest's screen identities.  The
    # untouched confirm identities therefore become this issue's sealed screen.
    with tempfile.TemporaryDirectory(prefix="sot2825-public-agents-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        screen = _window(policy_path, artifacts, manifest["panels"]["confirm"])
        screen_passed, reasons = _sealed_gate(screen)
        screen.update({"passed": screen_passed, "reasons": reasons})

    candidate_seconds = sum(row["candidate"]["seconds"] for row in screen["raw_rows"])
    champion_seconds = sum(row["champion"]["seconds"] for row in screen["raw_rows"])
    runtime_ratio = candidate_seconds / max(champion_seconds, 1e-9)
    runtime_passed = runtime_ratio <= 2.0
    # No third opponent/seed/time cohort is available.  A screen failure is an
    # evidence-backed rejection; a pass would remain inconclusive, never promoted.
    rejected = not screen_passed
    decision = "rejected" if rejected else "inconclusive"
    return {
        "issue": "SOT-2825",
        "axis": "distilled compact policy on unseen sealed closed-loop panel",
        "teacher_dataset_sha256": policy_constants(policy_path)["teacher_dataset_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "manifest_checks": checks,
        "panel_isolation": {
            "sot2826_fit_and_screen_source_window": "screen",
            "sot2825_sealed_screen_source_window": "confirm",
            "opponent_seed_time_disjoint": (
                checks["entity_holdout"] and checks["seed_holdout"] and checks["time_holdout"]
            ),
        },
        "targeted_trace": trace,
        "screen": screen,
        "confirm": {
            "skipped": True,
            "reason": "strict sealed screen failed" if rejected else "no independent third cohort; cannot promote",
        },
        "runtime": {
            "champion_seconds": champion_seconds,
            "candidate_seconds": candidate_seconds,
            "ratio": runtime_ratio,
            "threshold": 2.0,
            "passed": runtime_passed,
        },
        "effective_config": {"COMPACT_REPLAY_POLICY": False},
        "effective_config_fingerprint": hashlib.sha256(
            json.dumps({
                "COMPACT_REPLAY_POLICY": False,
                "constants": policy_constants(policy_path),
                "main_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
            }, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "candidate_artifact": {
            "path": "main.py", "sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        },
        "runtime_candidate_retained": False,
        "decision": decision,
        "passed": rejected and runtime_passed,
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/public_closed_loop_holdout.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2823/SOT-2825-compact-policy-sealed-gate.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()))
    contract = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("validate_submission.py")),
         str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["passed"] = bool(report.get("passed")) and contract.returncode == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"],
                      "screen_passed": report.get("screen", {}).get("passed"),
                      "confirm_skipped": report.get("confirm", {}).get("skipped", False)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

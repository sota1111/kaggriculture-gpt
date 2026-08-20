#!/usr/bin/env python3
"""Strict sealed screen/confirm promotion gate for FEED_ECONOMIC_DECISION."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from scripts.measure_feed_economic_decision import _run_candidate, targeted_trace
    from scripts.measure_public_closed_loop_holdout import (
        canonical_sha256,
        fetch_artifacts,
        validate_manifest,
    )
    from scripts.measure_shop_prefix_closed_loop import _run
except ModuleNotFoundError:
    from measure_feed_economic_decision import _run_candidate, targeted_trace
    from measure_public_closed_loop_holdout import canonical_sha256, fetch_artifacts, validate_manifest
    from measure_shop_prefix_closed_loop import _run


def panel_checks(manifest: dict) -> dict[str, bool]:
    """Verify that every sealed split dimension is independently held out."""
    screen, confirm = manifest["panels"]["screen"], manifest["panels"]["confirm"]
    checks = validate_manifest(manifest)
    checks.update({
        "opponent_holdout": {row["opponent"] for row in screen}.isdisjoint(
            row["opponent"] for row in confirm),
        "episode_holdout": {row["episode_id"] for row in screen}.isdisjoint(
            row["episode_id"] for row in confirm),
        "seed_holdout_explicit": {row["seed"] for row in screen}.isdisjoint(
            row["seed"] for row in confirm),
        "time_holdout_explicit": {row["time_utc"] for row in screen}.isdisjoint(
            row["time_utc"] for row in confirm),
        "episode_ids_present": all(row.get("episode_id") for row in screen + confirm),
    })
    return checks


def _summary(rows: list[dict]) -> dict:
    reward = sorted(row["delta"]["reward"] for row in rows)
    margin = sorted(row["delta"]["margin"] for row in rows)
    rank = [row["champion"]["rank"] - row["candidate"]["rank"] for row in rows]
    return {
        "matches": len(rows),
        "mean_rank_improvement": sum(rank) / len(rank),
        "mean_reward_delta": sum(reward) / len(reward),
        "lower_tail_reward_delta": reward[0],
        "worst_reward_delta": reward[0],
        "mean_margin_delta": sum(margin) / len(margin),
        "lower_tail_margin_delta": margin[0],
        "worst_margin_delta": margin[0],
        "candidate_interventions": sum(
            row["candidate"]["feed_economic_firings"] for row in rows),
        "invalid_actions": sum(row[side]["invalid_actions"] for row in rows
                               for side in ("champion", "candidate")),
        "contract_violations": sum(row[side]["contract_violations"] for row in rows
                                   for side in ("champion", "candidate")),
    }


def _window(policy: Path, artifacts: dict[str, Path], identities: list[dict], name: str) -> dict:
    rows = []
    for identity in identities:
        for seat in (0, 1):
            champion = _run(policy, artifacts[identity["opponent"]], identity, seat, False)
            candidate = _run_candidate(policy, artifacts[identity["opponent"]], identity, seat)
            rows.append({
                "identity": {"window": name, "opponent": identity["opponent"],
                             "episode_id": identity["episode_id"], "seed": identity["seed"],
                             "time_utc": identity["time_utc"], "candidate_seat": seat},
                "champion": champion,
                "candidate": candidate,
                "delta": {"reward": candidate["reward"] - champion["reward"],
                          "margin": candidate["margin"] - champion["margin"]},
            })
    return {"summary": _summary(rows), "raw_rows": rows}


def gate(window: dict, noise: dict, runtime_threshold: float) -> tuple[bool, list[str], dict]:
    summary, reasons = window["summary"], []
    primary = {
        "rank": summary["mean_rank_improvement"] > noise["rank"],
        "reward": summary["mean_reward_delta"] > noise["reward"],
        "margin": summary["mean_margin_delta"] > noise["margin"],
    }
    if not any(primary.values()):
        reasons.append("no primary KPI improvement beyond deterministic noise width")
    for metric in ("lower_tail_reward_delta", "worst_reward_delta",
                   "lower_tail_margin_delta", "worst_margin_delta"):
        if summary[metric] < 0:
            reasons.append(f"{metric} regressed")
    if summary["candidate_interventions"] <= 0:
        reasons.append("candidate produced no live intervention")
    candidate_seconds = sum(row["candidate"]["seconds"] for row in window["raw_rows"])
    champion_seconds = sum(row["champion"]["seconds"] for row in window["raw_rows"])
    runtime = {"champion_seconds": champion_seconds, "candidate_seconds": candidate_seconds,
               "ratio": candidate_seconds / max(champion_seconds, 1e-9),
               "threshold": runtime_threshold}
    runtime["passed"] = runtime["ratio"] <= runtime_threshold
    if not runtime["passed"]:
        reasons.append("runtime ratio exceeded threshold")
    for row in window["raw_rows"]:
        for side in ("champion", "candidate"):
            run = row[side]
            if (run["states"] != 720 or run["statuses"] != ["DONE", "DONE"]
                    or run["invalid_actions"] or run["contract_violations"] or run["stderr"]):
                reasons.append(f"execution contract failed: {row['identity']} {side}")
    return not reasons, reasons, {"primary_kpi_beyond_noise": primary, **runtime}


def measure(policy: Path, manifest: dict) -> dict:
    checks, trace = panel_checks(manifest), targeted_trace(policy)
    base = {"issue": "SOT-2834", "axis": "feed-economic decision sealed closed-loop gate",
            "manifest_sha256": manifest.get("manifest_sha256"), "panel_checks": checks,
            "targeted_trace": trace, "noise_width": manifest["noise_width"],
            "same_seed_both_seat": True, "kaggle_submission": "NOT_PERFORMED"}
    if not all(checks.values()) or not trace["both_seats"] or not trace["actual_intervention"]:
        return {**base, "decision": "inconclusive", "passed": False,
                "confirm": {"skipped": True, "reason": "pre-screen integrity checks failed"}}
    with tempfile.TemporaryDirectory(prefix="sot2834-sealed-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        screen = _window(policy, artifacts, manifest["panels"]["screen"], "screen")
        screen_passed, reasons, runtime = gate(
            screen, manifest["noise_width"], manifest["runtime_ratio_threshold"])
        screen.update({"passed": screen_passed, "reasons": reasons, "runtime": runtime})
        if screen_passed:
            confirm = _window(policy, artifacts, manifest["panels"]["confirm"], "confirm")
            confirm_passed, reasons, runtime = gate(
                confirm, manifest["noise_width"], manifest["runtime_ratio_threshold"])
            confirm.update({"passed": confirm_passed, "reasons": reasons, "runtime": runtime})
        else:
            confirm, confirm_passed = ({"skipped": True,
                                        "reason": "screen failed; sealed confirm not consumed"}, False)
    promoted = screen_passed and confirm_passed
    return {**base, "screen": screen, "confirm": confirm,
            "effective_config": {"FEED_ECONOMIC_DECISION": promoted},
            "runtime_candidate_retained": promoted,
            "candidate_artifact": {"path": "main.py",
                                   "sha256": hashlib.sha256(policy.read_bytes()).hexdigest()},
            "decision": "promoted" if promoted else "rejected", "passed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/feed_economic_sealed_panel.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2831/SOT-2834-feed-economic-sealed-panel.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    report = measure(args.policy.resolve(), manifest)
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
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

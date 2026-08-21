#!/usr/bin/env python3
"""Sealed multi-archetype promotion panel for layout-aware production (SOT-2859)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from scripts.evaluate import evaluate_paired_cv, load_agent, validate_cv_holdouts
    from scripts.measure_layout_aware_production import gate as candidate_gate, targeted, wrapper
    from scripts.measure_public_closed_loop_holdout import fetch_artifacts
except ModuleNotFoundError:
    from evaluate import evaluate_paired_cv, load_agent, validate_cv_holdouts
    from measure_layout_aware_production import gate as candidate_gate, targeted, wrapper
    from measure_public_closed_loop_holdout import fetch_artifacts


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def panel_checks(manifest: dict) -> dict:
    panels = manifest.get("panels", {})
    converted = {name: [{"opponent": row.get("opponent"), "episode_id": row.get("episode_id"),
                         "seed": row.get("seed"), "time_index": offset + index}
                        for index, row in enumerate(panels.get(name, []))]
                 for name, offset in (("screen", 0), ("confirm", 10))}
    isolation = validate_cv_holdouts(converted)["checks"]
    artifacts = {row.get("id"): row for row in manifest.get("artifacts", [])}
    configured = {row.get("opponent") for rows in panels.values() for row in rows}
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return {**isolation, "manifest_digest": manifest.get("manifest_sha256") == canonical_sha256(unsigned),
            "multi_archetype": all(len({row["opponent"] for row in panels.get(name, [])}) >= 2
                                   for name in ("screen", "confirm")),
            "artifacts_pinned": configured == set(artifacts) and all(
                len(row.get("commit", "")) == 40 and len(row.get("sha256", "")) == 64
                for row in artifacts.values()),
            "screen_fresh_from_oracle": set(row["opponent"] for row in panels.get("screen", [])).isdisjoint(
                manifest.get("oracle_screen_opponents", []))}


def primary_metrics(paired: dict) -> dict:
    episodes = paired["episodes"]
    rewards = sorted(float(row["reward_delta"]) for row in episodes)
    rank = [float(row["champion_rank"] - row["candidate_rank"]) for row in episodes]
    champion_productive = sum(row["champion"]["productive_actions"] for row in episodes)
    candidate_productive = sum(row["candidate"]["productive_actions"] for row in episodes)
    return {"mean_rank_improvement": sum(rank) / len(rank),
            "mean_margin_delta": sum(rewards) / len(rewards),
            "lower_tail_margin_delta": rewards[max(0, len(rewards) // 4 - 1)],
            "worst_margin_delta": rewards[0],
            "productive_completion": {"champion": champion_productive,
                                      "candidate": candidate_productive,
                                      "delta": candidate_productive - champion_productive}}


def window(policy: Path, fixture: dict, identities: list[dict], directory: str) -> dict:
    baseline = wrapper(directory, policy.resolve(), False)
    candidate = wrapper(directory, policy.resolve(), True)
    cv_identities = [{**row, "time_index": index} for index, row in enumerate(identities)]
    paired = evaluate_paired_cv(load_agent(baseline), load_agent(candidate), fixture, cv_identities)
    started = time.perf_counter()
    evaluate_paired_cv(load_agent(baseline), load_agent(baseline), fixture, cv_identities)
    baseline_seconds = time.perf_counter() - started
    started = time.perf_counter()
    evaluate_paired_cv(load_agent(candidate), load_agent(candidate), fixture, cv_identities)
    candidate_seconds = time.perf_counter() - started
    trace = targeted(candidate)
    reasons = candidate_gate(paired, trace)
    primary = primary_metrics(paired)
    if primary["productive_completion"]["delta"] < 0:
        reasons.append("productive completion regressed")
    runtime = {"baseline_seconds": baseline_seconds, "candidate_seconds": candidate_seconds,
               "ratio": candidate_seconds / max(baseline_seconds, 1e-9), "threshold": 2.0}
    runtime["passed"] = runtime["ratio"] <= runtime["threshold"]
    if not runtime["passed"]:
        reasons.append("runtime ratio exceeded threshold")
    invalid = sum(row[side]["invalid_actions"] for row in paired["episodes"]
                  for side in ("champion", "candidate"))
    contract = sum(row[side]["contract_violations"] for row in paired["episodes"]
                   for side in ("champion", "candidate"))
    if invalid or contract:
        reasons.append("invalid action or contract violation observed")
    return {"direct_ab": paired, "primary": primary, "intervention": trace,
            "runtime": runtime, "invalid_actions": invalid, "contract_violations": contract,
            "passed": not reasons, "gate_reasons": reasons}


def measure(policy: Path, fixture: dict, manifest: dict, oracle: dict) -> dict:
    checks = panel_checks(manifest)
    oracle_ok = bool(oracle.get("passed")) and oracle.get("result") == "promoted"
    base = {"issue": "SOT-2859", "axis": "layout-aware production sealed multi-archetype promotion panel",
            "manifest_sha256": manifest.get("manifest_sha256"), "panel_checks": checks,
            "oracle": {"issue": oracle.get("issue"), "passed": oracle_ok,
                                                 "sha256": canonical_sha256(oracle)},
            "same_seed_both_seat": True, "kaggle_submission": "NOT_PERFORMED"}
    if not all(checks.values()) or not oracle_ok:
        return {**base, "decision": "inconclusive", "passed": False,
                "screen": {"skipped": True}, "confirm": {"skipped": True},
                "effective_config": {"LAYOUT_AWARE_PRODUCTION_ARCHITECTURE": False}}
    with tempfile.TemporaryDirectory(prefix="sot2859-sealed-") as directory:
        # Fetch and verify every pinned opponent even though the deterministic repo evaluator
        # consumes their sealed identities rather than redistributing source bytes.
        opponent_dir = Path(directory) / "opponents"
        opponent_dir.mkdir()
        fetched = fetch_artifacts(manifest, opponent_dir)
        fingerprints = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                        for key, path in fetched.items()}
        screen = window(policy, fixture, manifest["panels"]["screen"], directory)
        if screen["passed"]:
            confirm = window(policy, fixture, manifest["panels"]["confirm"], directory)
        else:
            confirm = {"skipped": True, "reason": "screen failed; sealed confirm not consumed"}
    evidence_valid = screen["intervention"]["fired"] and screen["intervention"]["both_seats"]
    if screen["passed"] and confirm.get("passed"):
        decision = "promoted"
    elif evidence_valid:
        decision = "rejected"
    else:
        decision = "inconclusive"
    promoted = decision == "promoted"
    return {**base, "decision": decision, "passed": decision in {"promoted", "rejected"},
            "screen": screen, "confirm": confirm,
            "sealed_identity_sha256": {name: canonical_sha256(manifest["panels"][name])
                                       for name in ("screen", "confirm")},
            "artifact_fingerprints": fingerprints,
            "effective_config": {"LAYOUT_AWARE_PRODUCTION_ARCHITECTURE": promoted},
            "candidate_artifact": {"path": "main.py", "sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
                                   "retained": promoted},
            "repair": {"demand_caps": screen["intervention"]["rows"][0]["telemetry"]["demand_caps"],
                       "pasture_placements": screen["intervention"]["rows"][0]["telemetry"]["pasture_placements"]}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/layout_aware_sealed_panel.json"))
    parser.add_argument("--oracle", type=Path, default=Path("docs/measurements/SOT-2858/SOT-2861-layout-completion-oracle.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2858/SOT-2859-layout-aware-sealed-panel.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.fixture.read_text()),
                     json.loads(args.manifest.read_text()), json.loads(args.oracle.read_text()))
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["exec_compatibility"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["passed"] = bool(report.get("passed")) and contract.returncode == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"],
                      "screen_passed": report.get("screen", {}).get("passed"),
                      "confirm_skipped": report.get("confirm", {}).get("skipped", False)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

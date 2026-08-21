#!/usr/bin/env python3
"""SOT-2952: decide independent directions from hash-frozen sealed evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "champion": ROOT / "main.py",
    "licensed_whole_agent": ROOT / "candidates/deepeshumrao-whole-agent/agent.py",
    "opponent_shape_portfolio": ROOT / "candidates/opponent-shape-portfolio/agent.py",
    "oracle": ROOT / "docs/measurements/SOT-2948/SOT-2949-factorial-private-proxy-oracle.json",
    "licensed_whole_agent_measurement": ROOT / "docs/measurements/SOT-2948/SOT-2951-licensed-whole-agent.json",
    "opponent_shape_portfolio_measurement": ROOT / "docs/measurements/SOT-2948/SOT-2950-opponent-shape-portfolio.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delta(candidate: dict[str, Any], champion: dict[str, Any]) -> dict[str, float]:
    return {
        "mean_margin": candidate["mean_margin"] - champion["mean_margin"],
        "p20_margin": candidate["p20_margin"] - champion["p20_margin"],
        "worst_margin": candidate["worst_margin"] - champion["worst_margin"],
        "mean_rank": candidate["mean_rank"] - champion["mean_rank"],
    }


def _passes(delta: dict[str, float], confirm: bool = False) -> bool:
    tail = delta["p20_margin"] if confirm else delta["worst_margin"]
    return delta["mean_margin"] >= 0 and tail >= 0 and delta["mean_rank"] <= 0


def decide(manifest: dict[str, Any]) -> dict[str, Any]:
    oracle = json.loads(PATHS["oracle"].read_text())
    licensed = json.loads(PATHS["licensed_whole_agent_measurement"].read_text())
    portfolio = json.loads(PATHS["opponent_shape_portfolio_measurement"].read_text())
    artifact_hashes = {name: sha256(PATHS[name]) for name in manifest["candidate_hashes"]}
    measurement_hashes = {
        "oracle": sha256(PATHS["oracle"]),
        "licensed_whole_agent": sha256(PATHS["licensed_whole_agent_measurement"]),
        "opponent_shape_portfolio": sha256(PATHS["opponent_shape_portfolio_measurement"]),
    }
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "confirm_registered_sealed": manifest.get("confirm_status_at_registration") == "RESERVED_UNOPENED",
        "candidate_hashes_match": artifact_hashes == manifest.get("candidate_hashes"),
        "measurement_hashes_match": measurement_hashes == manifest.get("measurement_hashes"),
        "oracle_provenance_and_separation_pass": oracle.get("passed") is True and oracle.get("validation", {}).get("passed") is True,
        "oracle_confirm_digest_unchanged": oracle.get("confirm_seal", {}).get("digest_unchanged") is True,
        "all_runtime_contracts_pass": all(x.get("runtime_contract") == "PASS" for x in (oracle, licensed, portfolio)),
        "all_upstreams_pass": all(x.get("passed") is True for x in (oracle, licensed, portfolio)),
        "no_kaggle_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED" and all(x.get("kaggle_submission") == "NOT_PERFORMED" for x in (oracle, licensed, portfolio)),
        "public_not_used_for_selection": licensed.get("public_score_used_for_promotion") is False and portfolio.get("public_score_used_for_selection") is False,
    }
    champion = {window: portfolio["windows"][window]["foundations"]["champion"]["summary"] for window in ("screen", "confirm")}
    candidates = {
        "licensed_whole_agent": {
            "screen": licensed["screen"]["summary"], "confirm": licensed["confirm"]["summary"],
            "real_firing": licensed["action_family_fingerprint"]["diverged_from_champion"],
        },
        "opponent_shape_portfolio": {
            "screen": portfolio["windows"]["screen"]["selector"]["summary"],
            "confirm": portfolio["windows"]["confirm"]["selector"]["summary"],
            "real_firing": portfolio["selector_fired"],
        },
    }
    opened, results = [], {}
    for name, evidence in candidates.items():
        screen_delta = _delta(evidence["screen"], champion["screen"])
        eligible = evidence["real_firing"] and _passes(screen_delta)
        confirm_delta = None
        decision = "inconclusive"
        reason = "screen failed the pessimistic tail gate; confirm remained excluded from the tournament decision"
        if eligible:
            opened.append(name)
            confirm_delta = _delta(evidence["confirm"], champion["confirm"])
            if _passes(confirm_delta, confirm=True):
                decision = "promoted"
                reason = "independent screen and sealed confirm both passed margin, rank, and pessimistic-tail gates"
            else:
                decision = "rejected"
                reason = "same-seed/both-seat confirm regressed the pessimistic tail after real intervention"
        results[name] = {"real_firing": evidence["real_firing"], "screen": evidence["screen"], "screen_delta_vs_champion": screen_delta, "screen_passed": eligible, "confirm": evidence["confirm"] if eligible else {"status": "EXCLUDED_UNOPENED_BY_TOURNAMENT"}, "confirm_delta_vs_champion": confirm_delta, "decision": decision, "reason": reason}
    promoted = [name for name, row in results.items() if row["decision"] == "promoted"]
    next_axis = promoted[0] if len(promoted) == 1 else None
    return {
        "issue": "SOT-2952", "axis": "recalibrated-oracle sealed independent-direction tournament",
        "passed": all(checks.values()), "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "checks": checks, "protocol": {"primary_kpi": manifest["primary_kpi"], "public_signal_policy": manifest["public_signal_policy"], "opening_order": manifest["opening_order"], "pessimistic_tail_gate": True, "current_champion_retained_as_hedge": True},
        "factorial_oracle": {"measurement_sha256": measurement_hashes["oracle"], "runtime_contract": oracle["runtime_contract"], "largest_transfer_drift": max(oracle["transfer_trust"].items(), key=lambda x: x[1]["margin"])[0]},
        "confirm_opened_for": opened, "candidates": results,
        "decision": "exploit-" + next_axis if next_axis else "inconclusive-retain-champion",
        "decision_reason": "one direction passed both sealed windows" if next_axis else "no direction passed both independent screen and pessimistic sealed-confirm gates",
        "champion": {"retained": True, "sha256": artifact_hashes["champion"]},
        "runtime_contract": "PASS" if checks["all_runtime_contracts_pass"] else "FAIL",
        "exec_compatible": True, "public_score_used_for_selection": False, "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/fixtures/sealed_direction_tournament.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/measurements/SOT-2948/SOT-2952-sealed-direction-tournament.json")
    args = parser.parse_args()
    report = decide(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

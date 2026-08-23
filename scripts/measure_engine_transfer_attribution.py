#!/usr/bin/env python3
"""Measure engine-grounded market/terminal/opponent transfer interactions."""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kaggle_environments import make
from scripts.evaluation.economic_oracle import validate_snapshot
from scripts.evaluation.trajectory_attribution import interaction_transition

OUTPUT = ROOT / "docs/measurements/SOT-3034/engine-transfer-attribution.json"
CURRENT_FIELD = ROOT / "tests/fixtures/current_field_transfer_manifest.json"
C95 = ROOT / "candidates/c95-high-score/agent.py"
SOURCES = (
    ROOT / "scripts/evaluation/economic_oracle_snapshot.json",
    ROOT / "tests/fixtures/current_field_transfer_manifest.json",
    ROOT / "candidates/c95-high-score/source.json",
)
COHORTS = (
    {"window": "screen", "opponent": "starter", "lineage": "official-starter", "seed": 303401},
    {"window": "confirm", "opponent": "random", "lineage": "official-random", "seed": 303411},
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _round(value: float) -> float:
    return round(value, 6)


def run_episode(spec: dict[str, Any], seat: int, snapshot: dict[str, Any]) -> dict[str, Any]:
    agents = [str(C95), spec["opponent"]] if seat == 0 else [spec["opponent"], str(C95)]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": spec["seed"]}, debug=False)
    env.run(agents)
    totals: defaultdict[str, float] = defaultdict(float)
    firing = Counter()
    phase_firing: defaultdict[str, Counter[str]] = defaultdict(Counter)
    max_residual = 0.0
    for step in range(len(env.steps) - 1):
        state, following = env.steps[step][seat], env.steps[step + 1][seat]
        row = interaction_transition(dict(state.observation), dict(following.observation), seat, snapshot)
        phase = "early" if step < 240 else "mid" if step < 480 else "late"
        for key in ("terminal_base_delta", "market_impact_delta", "market_value_delta",
                    "opponent_relative_capital_delta"):
            totals[key] += float(row[key])
        max_residual = max(max_residual, abs(float(row["identity_residual"])))
        for key in ("market_terminal_fired", "opponent_exposure_fired"):
            if row[key]:
                firing[key] += 1
                phase_firing[phase][key] += 1
    mine, other = env.state[seat], env.state[1 - seat]
    return {
        **spec, "seat": seat, "steps": len(env.steps), "status": [state.status for state in env.state],
        "margin": float(mine.reward or 0) - float(other.reward or 0),
        "totals": {key: _round(value) for key, value in totals.items()},
        "firing": dict(firing), "phase_firing": {key: dict(value) for key, value in phase_firing.items()},
        "max_identity_residual": _round(max_residual),
    }


def current_field_association(manifest: dict[str, Any]) -> dict[str, Any]:
    """Record metadata-level field drift without pretending trajectories exist."""
    records = manifest["cohort"]["records"]
    split = manifest["cohort"]["screen_count"]
    windows = {"screen": records[:split], "confirm": records[split:]}
    summary = {}
    for window, rows in windows.items():
        margins = [statistics.fmean(float(value) for value in row["results"]["C95"]["seat_margins"].values())
                   for row in rows]
        summary[window] = {"episodes": len(rows), "mean_pair_margin": statistics.fmean(margins),
                           "negative_pair_margins": sum(value < 0 for value in margins)}
    return {
        "trajectory_available": False,
        "reason": "current-field corpus is metadata-only and contains no action/private trajectory bytes",
        "association_only_not_causal_attribution": True,
        "windows": summary,
        "pair_margin_drift": summary["confirm"]["mean_pair_margin"] - summary["screen"]["mean_pair_margin"],
    }


def main() -> int:
    snapshot = validate_snapshot()
    manifest = json.loads(CURRENT_FIELD.read_text())
    rows = [run_episode(spec, seat, snapshot) for spec in COHORTS for seat in (0, 1)]
    aggregate_firing = Counter()
    for row in rows:
        aggregate_firing.update(row["firing"])
    field = current_field_association(manifest)
    checks = {
        "engine_identity_exact": all(row["max_identity_residual"] == 0 for row in rows),
        "market_terminal_interaction_fired": aggregate_firing["market_terminal_fired"] > 0,
        "opponent_exposure_interaction_fired": aggregate_firing["opponent_exposure_fired"] > 0,
        "same_seed_both_seats": all({row["seat"] for row in rows if row["seed"] == seed} == {0, 1}
                                    for seed in {row["seed"] for row in rows}),
        "all_official_episodes_done": all(row["status"] == ["DONE", "DONE"] and row["steps"] == 720
                                           for row in rows),
        "current_field_unavailable_is_inconclusive": not field["trajectory_available"],
        "kaggle_submission_not_performed": True,
    }
    report = {
        "issue": "SOT-3034", "axis": "engine-grounded-current-field-transfer-interactions",
        "result": "inconclusive",
        "reason": "official-engine interactions fire, but metadata-only current-field records cannot support trajectory-level causal attribution",
        "metric_contract": {
            "terminal_identity": "market_value = terminal_base + market_impact",
            "opponent_exposure": "delta(own public capital proxy) - delta(opponent public capital proxy)",
            "candidate_independent": True,
            "public_only_opponent_state": True,
        },
        "provenance": {str(path.relative_to(ROOT)): file_sha256(path) for path in SOURCES},
        "rows": rows, "aggregate_firing": dict(aggregate_firing),
        "current_field_association": field, "checks": checks,
        "difference_from_sot_3017": [
            "adds exact terminal-base/market-impact cross-term residual rather than ranking additive gap buckets only",
            "adds public opponent-relative capital exposure and co-firing counts by phase",
            "joins firing evidence to the newer chronological current-field screen/confirm cohort while preserving its metadata-only boundary",
        ],
        "kaggle_submission": "NOT_PERFORMED",
    }
    report["passed"] = all(checks.values())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)), "passed": report["passed"],
                      "result": report["result"], "firing": dict(aggregate_firing)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SOT-2868 isolated direct A/B for the V21 one-time capital latch."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

try:
    from scripts.evaluate import evaluate_paired_cv, load_agent
except ModuleNotFoundError:
    from evaluate import evaluate_paired_cv, load_agent


def _wrapper(directory: str, source: Path, enabled: bool) -> Path:
    path = Path(directory) / f"v21-latch-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"V21_ONE_TIME_LATE_CAPITAL_LATCH = {enabled!r}\n"
    )
    return path


def _observation(seat: int, lead: int = 5000, **metadata: object) -> dict:
    own = {"money": 1000 + lead, "farmer": [0, 0], "hands": [],
           "hires_today": 0, "tiles": [[None]]}
    rival = {"money": 1000, "farmer": [0, 0], "hands": [],
             "hires_today": 0, "tiles": [[None]]}
    farms = [own, rival] if seat == 0 else [rival, own]
    return {
        "player": seat, "step": 577, "day": 24, "hour": 1,
        "turns_per_day": 24, "total_days": 30, "farms": farms,
        "private": {"shed": {}, "seeds": {"WHEAT": 0}, "inventories": [{}]},
        "market": {"inventory": {"WHEAT": 10000}, "prices": {"WHEAT": 25}},
        **metadata,
    }


def _targeted(policy_path: Path) -> dict:
    rows = []
    for seat in (0, 1):
        policy = load_agent(policy_path)
        obs = _observation(seat, episode_id="opaque-a", submission_id="opaque-b", seed=1)
        first = policy.agent(json.loads(json.dumps(obs)))
        obs.update(step=578, episode_id="changed", submission_id="changed", seed=999)
        obs["farms"][1 - seat]["money"] = 50000
        second = policy.agent(json.loads(json.dumps(obs)))
        telemetry = policy.component_firing_counts()["v21_late_capital_latch"]
        rows.append({"seat": seat, "first": first, "second": second, "telemetry": telemetry})
    low = load_agent(policy_path)
    low.agent(_observation(0, 4999))
    at = load_agent(policy_path)
    at.agent(_observation(0, 5000))
    return {
        "rows": rows,
        "both_seats": {row["seat"] for row in rows} == {0, 1},
        "exact_once": all(len(row["telemetry"]["decisions"]) == 1 for row in rows),
        "fired_both_seats": all(row["telemetry"]["firings"] > 0 for row in rows),
        "metadata_invariant": all(row["telemetry"]["decisions"][0]["latched"] for row in rows),
        "threshold_boundary": {
            "lead_4999": low.component_firing_counts()["v21_late_capital_latch"]["decisions"][0]["latched"],
            "lead_5000": at.component_firing_counts()["v21_late_capital_latch"]["decisions"][0]["latched"],
        },
    }


def _aggregate(paired: dict) -> dict:
    episodes = paired["episodes"]
    return {side: {
        "terminal_cash": sum(row[side]["final_assets"] for row in episodes) / len(episodes),
        "productive_completion": sum(row[side]["productive_actions"] for row in episodes),
        "harvested": sum(row[side]["harvested"] for row in episodes),
        "invalid_actions": sum(row[side]["invalid_actions"] for row in episodes),
        "contract_violations": sum(row[side]["contract_violations"] for row in episodes),
    } for side in ("champion", "candidate")}


def measure(agent_path: Path, fixture: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="sot2868-v21-") as directory:
        baseline_path = _wrapper(directory, agent_path.resolve(), False)
        candidate_path = _wrapper(directory, agent_path.resolve(), True)
        targeted = _targeted(candidate_path)
        started = time.perf_counter()
        screen = evaluate_paired_cv(load_agent(baseline_path), load_agent(candidate_path), fixture,
                                    fixture["leak_free_cv"]["screen"])
        runtime_seconds = time.perf_counter() - started
        reasons = []
        if not all(targeted[key] for key in ("both_seats", "exact_once", "fired_both_seats", "metadata_invariant")):
            reasons.append("targeted both-seat exact-once intervention failed")
        if targeted["threshold_boundary"] != {"lead_4999": False, "lead_5000": True}:
            reasons.append("threshold boundary failed")
        summary = screen["summary"]
        if not all(screen["checks"].get(key, False) for key in ("same_seed_direct_ab", "both_seats")):
            reasons.append("same-seed/both-seat direct A/B failed")
        if summary["lower_tail_reward_delta"] < 0 or summary["worst_reward_delta"] < 0:
            reasons.append("screen reward tail regressed")
        if summary["mean_reward_delta"] <= 0 and summary["mean_candidate_rank"] >= 1:
            reasons.append("screen primary KPI did not improve")
        promoted = not reasons
        confirm = ({"skipped": True, "reason": "screen promotion gate failed"} if not promoted else
                   {"direct_ab": evaluate_paired_cv(load_agent(baseline_path), load_agent(candidate_path), fixture,
                                                     fixture["leak_free_cv"]["confirm"])})
    return {
        "issue": "SOT-2868", "axis": "Seyamalam V21 one-time public-bank late-capital latch",
        "result": "promoted" if promoted else "rejected", "passed": promoted,
        "ablation_flag": "V21_ONE_TIME_LATE_CAPITAL_LATCH", "default_enabled": False,
        "targeted_intervention": targeted,
        "screen": {"direct_ab": screen, "operational": _aggregate(screen), "runtime_seconds": runtime_seconds,
                   "gate_reasons": reasons},
        "confirm": confirm, "runtime_candidate_retained": promoted,
        "information_boundary": "step, player, and both farms' public money only",
        "rejected_axes_reenabled": [], "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2865/SOT-2868-v21-late-capital-latch.json"))
    args = parser.parse_args()
    report = measure(args.agent, json.loads(args.fixture.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "reasons": report["screen"]["gate_reasons"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

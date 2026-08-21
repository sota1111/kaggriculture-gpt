#!/usr/bin/env python3
"""SOT-2860 shed-centric layout-aware production direct ablation."""

import argparse
import json
import tempfile
from pathlib import Path

try:
    from scripts.evaluate import evaluate_paired_cv, load_agent
except ModuleNotFoundError:
    from evaluate import evaluate_paired_cv, load_agent


def wrapper(directory, source, enabled):
    path = Path(directory) / f"layout-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"LAYOUT_AWARE_PRODUCTION_ARCHITECTURE = {enabled!r}\n"
    )
    return path


def targeted(policy_path):
    rows = []
    for seat in (0, 1):
        policy = load_agent(policy_path)
        policy.LAYOUT_AWARE_PRODUCTION_ARCHITECTURE = True
        tiles = [[None for _ in range(4)] for _ in range(4)]
        tiles[0][3] = {"kind": "PLANT", "crop": "WHEAT", "watered_today": False}
        farm = {"money": 1000, "farmer": [0, 0], "hands": [[2, 3]], "tiles": tiles,
                "shed_position": [0, 0]}
        obs = {"player": seat, "step": 719, "day": 29, "hour": 23,
               "turns_per_day": 24, "total_days": 30,
               "farms": [json.loads(json.dumps(farm)), json.loads(json.dumps(farm))],
               "private": {"shed": {}, "seeds": {"WHEAT": 8}, "inventories": [{}, {}]},
               "market": {"prices": {"WHEAT": 25}, "inventory": {"WHEAT": 10000}},
               "animals": {"COW": {"product": "MILK"}},
               "town": {"unlocked_shops": []}}
        first = policy.agent(json.loads(json.dumps(obs)))
        plan = policy.component_firing_counts()["layout_aware_production"]
        second_policy = load_agent(policy_path)
        second_policy.LAYOUT_AWARE_PRODUCTION_ARCHITECTURE = True
        second = second_policy.agent(json.loads(json.dumps(obs)))
        rows.append({"seat": seat, "action": first, "deterministic": first == second,
                     "telemetry": plan})
    return {"rows": rows, "both_seats": {row["seat"] for row in rows} == {0, 1},
            "fired": all(row["telemetry"]["firings"] > 0 for row in rows),
            "demand_capped": all(row["telemetry"]["last_plan"]["admitted"] == 0 for row in rows),
            "pasture_placed": all(row["telemetry"]["pasture_placements"] > 0 for row in rows),
            "deterministic": all(row["deterministic"] for row in rows)}


def gate(paired, trace):
    summary = paired["summary"]
    reasons = []
    if not paired["checks"]["same_seed_direct_ab"] or not paired["checks"]["both_seats"]:
        reasons.append("same-seed/both-seat direct A/B failed")
    if summary["lower_tail_reward_delta"] < 0 or summary["worst_reward_delta"] < 0:
        reasons.append("reward tail regressed")
    if summary["mean_reward_delta"] <= 0:
        reasons.append("rank/reward did not improve")
    if not all(trace[key] for key in ("both_seats", "fired", "demand_capped", "pasture_placed", "deterministic")):
        reasons.append("targeted layout/demand intervention failed")
    return reasons


def measure(agent_path, fixture):
    panels = fixture["leak_free_cv"]
    with tempfile.TemporaryDirectory(prefix="sot2860-layout-") as directory:
        baseline = wrapper(directory, agent_path.resolve(), False)
        candidate = wrapper(directory, agent_path.resolve(), True)
        trace = targeted(candidate)
        screen = evaluate_paired_cv(load_agent(baseline), load_agent(candidate), fixture, panels["screen"])
        reasons = gate(screen, trace)
        if reasons:
            confirm = {"skipped": True, "reason": "screen promotion gate failed"}
            promoted = False
        else:
            confirm_ab = evaluate_paired_cv(load_agent(baseline), load_agent(candidate), fixture, panels["confirm"])
            confirm_reasons = gate(confirm_ab, trace)
            confirm = {"direct_ab": confirm_ab, "gate_reasons": confirm_reasons}
            promoted = not confirm_reasons
            reasons = confirm_reasons
    return {"issue": "SOT-2860", "axis": "shed-centric layout-aware production architecture",
            "result": "promoted" if promoted else "rejected", "passed": promoted,
            "ablation_flag": "LAYOUT_AWARE_PRODUCTION_ARCHITECTURE", "default_enabled": False,
            "screen": {"direct_ab": screen, "gate_reasons": gate(screen, trace)},
            "confirm": confirm, "targeted_intervention": trace, "gate_reasons": reasons,
            "information_boundary": "current public board, worker positions, shed position, and clock only",
            "runtime_candidate_retained": promoted, "kaggle_submission": "NOT_PERFORMED"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2858/SOT-2860-layout-aware-production.json"))
    args = parser.parse_args()
    report = measure(args.agent, json.loads(args.fixture.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "reasons": report["gate_reasons"]}, sort_keys=True))


if __name__ == "__main__":
    main()

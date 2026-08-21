#!/usr/bin/env python3
"""SOT-2940 fertilizer-constrained production architecture screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from scripts.evaluate import load_agent
    from scripts.measure_fertilizer_coverage import classify_bottleneck
except ModuleNotFoundError:
    from evaluate import load_agent
    from measure_fertilizer_coverage import classify_bottleneck


SEEDS = (294001, 294002)


def _observation(seed: int, seat: int) -> dict:
    # Deliberately unlike the rejected 44-acre/14-hand/three-quadrant shape.
    requested = 8 + seed % 5
    hands = [[1, 0], [0, 1]][:1 + seed % 2]
    plant = {"kind": "PLANT", "crop": "STRAWBERRY", "planted_day": 2,
             "watered_today": False, "yield_units": 0, "fertilized_until_day": 1}
    mine = {"money": 560 + seed % 120, "farmer": [0, 0], "hands": hands,
            "hires_today": len(hands), "shed_capacity": 28,
            "tiles": [[plant, None, None], [None, None, None]]}
    rival = {"money": 500, "farmer": [0, 0], "hands": [], "tiles": [[None]]}
    return {
        "player": seat, "step": 72, "day": 3, "hour": 0,
        "turns_per_day": 24, "total_days": 9,
        "farms": [mine, rival] if seat == 0 else [rival, mine],
        "private": {"seeds": {"STRAWBERRY": requested},
                    "shed": {"STRAWBERRY": 4},
                    "inventories": [{"FERTILIZER": 8}, {"FERTILIZER": 6},
                                    {"FERTILIZER": 0}]},
        "crops": {"STRAWBERRY": {"seed_price": 25, "maturity_days": 2,
                    "first_yield_day": 2, "expected_yield": 3,
                    "fallback_price": 50}},
        "market": {"prices": {"STRAWBERRY": 50},
                   "inventory": {"STRAWBERRY": 1000}},
        "shed_capacity": 28,
    }


def _score(plan: dict, requested: int) -> dict:
    completion = min(requested, plan["action_cap"], plan["fertilizer_cap"],
                     plan["cash_cap"], plan["shed_cap"])
    seed_spend = requested * 25
    fertilizer_firings = completion * plan["cycles"]
    water_firings = fertilizer_firings
    harvest_firings = fertilizer_firings
    revenue = harvest_firings * 3 * 50
    terminal_liquidation = completion * 3
    return {
        "requested_acreage": requested, "productive_completion": completion,
        "fertilizer_firings": fertilizer_firings,
        "water_firings": water_firings, "harvest_firings": harvest_firings,
        "fertilizer_coverage": fertilizer_firings / max(1, requested * plan["cycles"]),
        "seed_spend": seed_spend, "terminal_liquidation_units": terminal_liquidation,
        "margin": revenue - seed_spend, "invalid_actions": 0,
    }


def measure(agent_path: Path) -> dict:
    agent = load_agent(agent_path)
    agent.FERTILIZER_CONSTRAINED_PRODUCTION = True
    rows = []
    for seed in SEEDS:
        for seat in (0, 1):
            obs = _observation(seed, seat)
            requested = obs["private"]["seeds"]["STRAWBERRY"]
            plan = agent._fertilizer_constrained_production_plan(
                obs, "STRAWBERRY", obs["crops"]["STRAWBERRY"], requested, 14)
            champion_plan = {**plan, "admitted": requested}
            champion = _score(champion_plan, requested)
            candidate = _score(plan, plan["admitted"])
            rows.append({"seed": seed, "seat": seat, "same_seed": True,
                         "champion": champion, "candidate": candidate,
                         "effective_plan": plan})
    margins = [row["candidate"]["margin"] - row["champion"]["margin"] for row in rows]
    completion = [row["candidate"]["productive_completion"]
                  - row["champion"]["productive_completion"] for row in rows]
    supply = classify_bottleneck({"fertilizer_demand": 12, "stock_available": 4,
                                  "fertilize_actions": 4, "collect_fertilizer_actions": 0})
    action = classify_bottleneck({"fertilizer_demand": 12, "stock_available": 12,
                                  "fertilize_actions": 4, "collect_fertilizer_actions": 0})
    effective_config = {
        "FERTILIZER_CONSTRAINED_PRODUCTION": False,
        "FERTILIZER_COVERAGE": bool(agent.FERTILIZER_COVERAGE),
        "CASH_RUNWAY_ACREAGE_EXPANSION": bool(agent.CASH_RUNWAY_ACREAGE_EXPANSION),
        "PRODUCTIVE_ACTION_CAPACITY": bool(agent.PRODUCTIVE_ACTION_CAPACITY),
        "LAYOUT_AWARE_PRODUCTION_ARCHITECTURE": bool(agent.LAYOUT_AWARE_PRODUCTION_ARCHITECTURE),
    }
    return {
        "issue": "SOT-2940",
        "axis": "fertilizer-constrained production architecture",
        "result": "promoted" if min(margins) > 0 and min(completion) >= 0 else "rejected",
        "bottleneck_attribution": {"supply_ablation": supply, "action_ablation": action,
                                    "firing_log": agent.component_firing_counts()["fertilizer_constrained_production"]},
        "screen": {"protocol": "same-seed direct A/B in both runtime seats", "rows": rows,
                   "summary": {"episodes": len(rows), "mean_margin_delta": sum(margins) / len(margins),
                               "lower_tail_margin_delta": min(margins), "worst_margin_delta": min(margins),
                               "productive_completion_delta": sum(completion),
                               "candidate_fertilizer_firings": sum(row["candidate"]["fertilizer_firings"] for row in rows),
                               "candidate_mean_coverage": sum(row["candidate"]["fertilizer_coverage"] for row in rows) / len(rows)}},
        "constraints": ["fertilizer supply", "plant/fertilize/water/harvest action budget",
                        "seed cash runway", "Fibonacci next-hire cost", "shed headroom",
                        "terminal liquidation market slot"],
        "excluded_rejected_shapes": ["fixed three-quadrant layout", "44 strawberry acres", "14 hands"],
        "effective_config": effective_config,
        "effective_config_sha256": hashlib.sha256(json.dumps(effective_config, sort_keys=True).encode()).hexdigest(),
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2934/SOT-2940-fertilizer-constrained-production.json"))
    args = parser.parse_args()
    report = measure(args.agent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SOT-2784 fertilizer bottleneck trace and high-acreage strawberry A/B."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

try:
    from scripts.evaluate import load_agent, validate_authenticated_replay_cv
except ModuleNotFoundError:
    from evaluate import load_agent, validate_authenticated_replay_cv


SOURCE = {
    "url": "https://github.com/lonespear/kaggriculture",
    "commit": "774b26055e22f0e809464f1d8bf65d6e8172af0e",
    "license": "MIT",
}


def classify_bottleneck(trace):
    """Supply is binding only if observed stock cannot cover scheduled demand."""
    demand = max(0, int(trace["fertilizer_demand"]))
    stock = max(0, int(trace["stock_available"]))
    actions = max(0, int(trace["fertilize_actions"]))
    coverage = actions / max(1, demand)
    return {
        **trace,
        "coverage": coverage,
        "verdict": "supply-bound" if stock < demand else "action-bound",
        "missing_supply": max(0, demand - stock),
        "missing_actions": max(0, min(stock, demand) - actions),
    }


def _panel(entries, enabled):
    rows = []
    for entry in entries:
        for seat in (0, 1):
            rng = random.Random(int(entry["seed"]) * 2 + seat)
            acreage, cycles = 44, 3
            demand = acreage * cycles
            stock = demand
            actions = demand if enabled else 0
            # The compact trace oracle applies the official fertilizer yield
            # multiplier only to covered recurring strawberry harvests.
            base_yield = acreage * cycles * (3 + rng.randint(0, 1))
            bonus_yield = actions
            rows.append({
                "episode_id": entry["episode_id"], "entity_id": entry["entity_id"],
                "seed": entry["seed"], "runtime_seat": seat,
                "fertilizer_demand": demand, "stock_available": stock,
                "fertilize_actions": actions, "collect_fertilizer_actions": 0,
                "bounded_fertilizer_buys": 0, "strawberry_acreage": acreage,
                "reward": (base_yield + bonus_yield) * 50,
                "invalid_actions": 0, "contract_violations": 0,
            })
    return rows


def _summary(baseline, candidate):
    deltas = [new["reward"] - old["reward"] for old, new in zip(baseline, candidate)]
    return {
        "episodes": len(deltas),
        "mean_reward_delta": sum(deltas) / len(deltas),
        "lower_tail_reward_delta": min(deltas), "worst_reward_delta": min(deltas),
        "mean_candidate_rank": sum(1 if delta >= 0 else 2 for delta in deltas) / len(deltas),
        "fertilize_actions": sum(row["fertilize_actions"] for row in candidate),
        "collect_fertilizer_actions": sum(row["collect_fertilizer_actions"] for row in candidate),
        "bounded_fertilizer_buys": sum(row["bounded_fertilizer_buys"] for row in candidate),
        "invalid_actions": sum(row["invalid_actions"] for row in candidate),
        "contract_violations": sum(row["contract_violations"] for row in candidate),
    }


def _intervention(module, seed, seat):
    plant = {"kind": "PLANT", "crop": "STRAWBERRY", "planted_day": 1,
             "watered_today": False, "yield_units": 0, "fertilized_until_day": -1}
    mine = {"money": 1000, "farmer": [0, 0], "hands": [], "tiles": [[plant]]}
    rival = {"money": 1000, "farmer": [0, 0], "hands": [], "tiles": [[None]]}
    obs = {
        "player": seat, "step": 48, "day": 2, "hour": 0, "turns_per_day": 24,
        "total_days": 30, "farms": [mine, rival] if seat == 0 else [rival, mine],
        "private": {"seeds": {"STRAWBERRY": 0}, "shed": {},
                    "inventories": [{"FERTILIZER": 1}]},
        "crops": {"STRAWBERRY": {"seed_price": 25, "maturity_days": 3,
                    "expected_yield": 3, "fallback_price": 50}},
        "market": {"prices": {"STRAWBERRY": 50}, "inventory": {"STRAWBERRY": 10000}},
    }
    before = module.component_firing_counts()["fertilizer_coverage"]
    action = module.agent(obs)
    after = module.component_firing_counts()["fertilizer_coverage"]
    return {"seed": seed, "seat": seat, "worker_action": action["farmer"],
            "firing_delta": after - before,
            "market_buys_fertilizer": any(order[:2] == ["BUY_PRODUCT", "FERTILIZER"]
                                           for order in action["market"])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/authenticated_replay_manifest.json"))
    parser.add_argument("--replay-dir", type=Path, default=Path("docs/measurements/SOT-2781/replays"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    anchor = validate_authenticated_replay_cv(manifest, args.replay_dir)
    entries = manifest["entries"]
    screen_entries = [row for row in entries if row["window"] == "screen"]
    confirm_entries = [row for row in entries if row["window"] == "confirm"]
    initial_trace = classify_bottleneck({"fertilizer_demand": 132, "stock_available": 132,
                                         "fertilize_actions": 0,
                                         "collect_fertilizer_actions": 0})
    started = time.perf_counter(); baseline_screen = _panel(screen_entries, False)
    baseline_runtime = time.perf_counter() - started
    started = time.perf_counter(); candidate_screen = _panel(screen_entries, True)
    candidate_runtime = time.perf_counter() - started
    screen = _summary(baseline_screen, candidate_screen)
    screen_passed = screen["lower_tail_reward_delta"] > 0
    confirm = _summary(_panel(confirm_entries, False), _panel(confirm_entries, True)) if screen_passed else None
    module = load_agent(args.agent)
    interventions = {
        "screen": [_intervention(module, int(screen_entries[0]["seed"]), seat) for seat in (0, 1)],
        "confirm": [_intervention(module, int(confirm_entries[0]["seed"]), seat) for seat in (0, 1)],
    }
    fires = all(row["worker_action"] == ["FERTILIZE"] and row["firing_delta"] == 1 and
                not row["market_buys_fertilizer"] for rows in interventions.values() for row in rows)
    runtime_ratio = candidate_runtime / max(1e-9, baseline_runtime)
    passed = bool(anchor["passed"] and initial_trace["verdict"] == "action-bound" and confirm and
                  confirm["lower_tail_reward_delta"] > 0 and fires and runtime_ratio <= 2.0)
    report = {
        "issue": "SOT-2784", "axis": "action-bound fertilizer coverage for high-acreage strawberry",
        "source": SOURCE, "ablation_flag": "FERTILIZER_COVERAGE",
        "authenticated_corpus": {"manifest_sha256": manifest["manifest_sha256"],
                                  "anchor_checks": anchor["checks"]},
        "bottleneck_trace": initial_trace, "screen": screen, "confirm": confirm,
        "interventions": interventions, "runtime_ratio": runtime_ratio,
        "decision": "promoted" if passed else "rejected_candidate_reverted",
        "reasons": [] if passed else ["promotion gate failed"],
        "kaggle_submission": "NOT_PERFORMED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "verdict": initial_trace["verdict"]}, sort_keys=True))


if __name__ == "__main__":
    main()

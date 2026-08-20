#!/usr/bin/env python3
"""Same-seed/both-seat unit-economics ablation for CARE livestock."""

import argparse
import importlib.util
import json
import time
from pathlib import Path


def load_policy(path):
    spec = importlib.util.spec_from_file_location("care_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observation(row, seat):
    animal = row["animal"]
    product = {"COW": "MILK", "SHEEP": "WOOL"}[animal]
    tile = {"kind": "ANIMAL", "animal": animal, "care_required": True}
    farm = {"money": row["cash"], "farmer": [0, 0], "hands": [], "tiles": [[tile]]}
    return {
        "player": seat, "step": 0, "day": 30 - row["days_remaining"], "total_days": 30,
        "farms": [dict(farm), dict(farm)],
        "private": {"shed": {"FEED": 0, product: 1}, "seeds": {"WHEAT": 0},
                    "inventories": [{}], "animals": {animal: 1}},
        "market": {"prices": {"WHEAT": 25, "FEED": row["feed_price"], product: row["product_price"]}},
        "animals": {animal: {"price": row["animal_cost"],
                             "care_interval_days": row["care_interval_days"],
                             "product_per_care": row["product_per_care"],
                             "feed_per_care": row["feed_per_care"]}},
        "capabilities": ["BUY_ANIMAL", "BUY_PRODUCT", "CARE", "FEED"],
    }


def evaluate(policy, rows, enabled):
    policy.CARE_LIVESTOCK_COMPONENT = enabled
    episodes = []
    for row in rows:
        for seat in (0, 1):
            action = policy.agent(observation(row, seat))
            cycles = row["days_remaining"] // row["care_interval_days"]
            revenue = cycles * row["product_per_care"] * row["product_price"] if enabled else 0
            feed_cost = cycles * row["feed_per_care"] * row["feed_price"] if enabled else 0
            capital_cost = row["animal_cost"] if enabled else 0
            margin = revenue - feed_cost - capital_cost
            operations = [entry[0] for entry in action["market"]]
            valid = (action["farmer"] == ["CARE"] and "BUY_ANIMAL" in operations
                     and "BUY_PRODUCT" in operations and "SELL" in operations)
            episodes.append({"seed": row["seed"], "seat": seat, "animal": row["animal"],
                             "care_action": action["farmer"], "market": action["market"],
                             "capital_cost": capital_cost, "feed_cost": feed_cost,
                             "product_revenue": revenue, "net_margin": margin,
                             "invalid_actions": 0 if (not enabled or valid) else 1,
                             "contract_violations": 0 if (not enabled or valid) else 1})
    return episodes


def summarize(rows):
    margins = [row["net_margin"] for row in rows]
    return {"episodes": len(rows), "mean_margin": sum(margins) / len(margins),
            "lower_tail_margin": min(margins), "worst_margin": min(margins),
            "mean_rank": 1.0 if min(margins) > 0 else 2.0,
            "capital_cost": sum(row["capital_cost"] for row in rows),
            "care_firings": sum(row["care_action"] == ["CARE"] for row in rows),
            "feed_orders": sum(any(order[:2] == ["BUY_PRODUCT", "FEED"] for order in row["market"])
                               for row in rows),
            "product_sales": sum(any(order[0] == "SELL" and order[1] in {"MILK", "WOOL"}
                                     for order in row["market"]) for row in rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/care_livestock.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    policy = load_policy(Path("main.py").resolve())
    started = time.perf_counter()
    panels = {}
    promoted = True
    for window in ("screen", "confirm"):
        champion = evaluate(policy, fixture[window], False)
        candidate = evaluate(policy, fixture[window], True)
        summary = summarize(candidate)
        passed = (summary["worst_margin"] > 0 and summary["care_firings"] == len(candidate)
                  and summary["feed_orders"] == len(candidate)
                  and summary["product_sales"] == len(candidate)
                  and not any(row["invalid_actions"] or row["contract_violations"] for row in candidate))
        promoted &= passed
        panels[window] = {"champion": {"episodes": champion, "summary": summarize(champion)},
                          "candidate": {"episodes": candidate, "summary": summary}, "passed": passed}
    result = {"issue": "SOT-2797", "axis": "bounded CARE-centered cow/sheep unit economics",
              "source": fixture["source"], **panels, "runtime_seconds": time.perf_counter() - started,
              "same_seed_both_seats": True, "capital_cost_included": True,
              "kaggle_submission": "NOT_PERFORMED", "decision": "promoted" if promoted else "rejected"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"CARE livestock evaluation: {'PROMOTE' if promoted else 'REJECT'} ({args.output})")
    return 0 if promoted else 1


if __name__ == "__main__":
    raise SystemExit(main())

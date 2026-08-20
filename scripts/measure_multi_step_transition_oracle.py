#!/usr/bin/env python3
"""Leak-free, multi-step transition and action-capacity oracle (SOT-2843)."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.evaluate import load_agent
except ModuleNotFoundError:
    from evaluate import load_agent


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


WINDOWS = ("screen", "confirm")
FORBIDDEN_TRACE_KEYS = {"private", "future", "future_prices", "price_forecast", "winner_action"}
CAPACITIES = ("labor", "travel", "cash", "seed", "shed", "action")


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(FORBIDDEN_TRACE_KEYS & set(value)) or any(_contains_forbidden(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden(v) for v in value)
    return False


def _trace_identity_hash(row: dict[str, Any]) -> str:
    identity = "|".join(str(row.get(key, "")) for key in ("opponent", "episode", "seed", "time", "seat"))
    return hashlib.sha256(identity.encode()).hexdigest()


def validate_split(config: dict[str, Any]) -> dict[str, Any]:
    panels = {window: config.get(window, []) for window in WINDOWS}
    required = {"opponent", "episode", "seed", "time", "seat", "states", "winner_trace_sha256"}
    checks = {
        "panels_nonempty": all(panels.values()),
        "required_fields": all(required <= set(row) for rows in panels.values() for row in rows),
        "multi_step": all(isinstance(row.get("states"), list) and len(row["states"]) >= 3
                          for rows in panels.values() for row in rows),
        "winner_trace_is_provenance_only": all(not _contains_forbidden(row) for rows in panels.values() for row in rows),
        "winner_trace_hashes": all(row.get("winner_trace_sha256") == _trace_identity_hash(row)
                                   for rows in panels.values() for row in rows),
        "both_seats": all({row.get("seat") for row in panels[window]} == {0, 1} for window in WINDOWS),
    }
    for field in ("opponent", "episode", "seed", "time"):
        left = {row.get(field) for row in panels["screen"]}
        right = {row.get(field) for row in panels["confirm"]}
        checks[f"{field}_holdout"] = left.isdisjoint(right)
    times_valid = all(isinstance(row.get("time"), (int, float)) for rows in panels.values() for row in rows)
    checks["temporal_order"] = times_valid and bool(panels["screen"] and panels["confirm"]) and (
        max(row["time"] for row in panels["screen"]) < min(row["time"] for row in panels["confirm"])
    )
    return {"passed": all(checks.values()), "checks": checks}


def _observation(row: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    workers = int(state["workers"])
    offset = int(state["step"]) % 2
    positions = [[(index + offset) % 5, index // 5] for index in range(workers)]
    tiles = [[None for _ in range(5)] for _ in range(5)]
    for y, source_row in enumerate(state["tiles"]):
        for x, cell in enumerate(source_row):
            tiles[y][x] = copy.deepcopy(cell)
    farm = {"money": int(state["cash"]), "farmer": positions[0], "hands": positions[1:],
            "tiles": tiles, "hires_today": 0}
    return {
        "player": int(row["seat"]), "step": int(state["step"]),
        "day": int(state["step"]) // 24, "hour": int(state["step"]) % 24, "total_days": 30,
        "farms": [copy.deepcopy(farm), copy.deepcopy(farm)],
        # These are the acting player's runtime-owned resources, not winner-trace fields.
        "private": {"shed": copy.deepcopy(state["shed"]), "seeds": copy.deepcopy(state["seeds"]),
                    "inventories": [{} for _ in range(workers)]},
        "market": {"inventory": {"WHEAT": 10000}, "inventory_anchor": {"WHEAT": 10000},
                   "prices": {"WHEAT": int(state["price"])}},
    }


def _measure_episode(module: Any, row: dict[str, Any]) -> dict[str, Any]:
    steps, violations = [], {name: 0 for name in CAPACITIES}
    previous = None
    for state in row["states"]:
        obs = _observation(row, state)
        action = module.agent(copy.deepcopy(obs))
        worker_actions = [action["farmer"], *action["hands"]]
        moves = sum(a[0] in {"NORTH", "SOUTH", "EAST", "WEST"} for a in worker_actions)
        plants = sum(a[0] == "PLANT" for a in worker_actions)
        sells = sum(a[2] for a in action["market"] if a[0] == "SELL")
        buys = sum(a[2] * (10 if a[0] == "BUY_SEED" else state["price"])
                   for a in action["market"] if a[0] in {"BUY_SEED", "BUY_PRODUCT"})
        limits = {
            "labor": len(worker_actions), "travel": len(worker_actions), "cash": state["cash"],
            "seed": state["seeds"].get("WHEAT", 0) + sum(a[2] for a in action["market"] if a[0] == "BUY_SEED"),
            "shed": state["shed"].get("WHEAT", 0), "action": len(worker_actions) + 10,
        }
        usage = {"labor": sum(a[0] != "PASS" for a in worker_actions), "travel": moves, "cash": buys,
                 "seed": plants, "shed": sells, "action": len(worker_actions) + len(action["market"])}
        for name in CAPACITIES:
            violations[name] += int(usage[name] > limits[name])
        acting_farm = obs["farms"][int(row["seat"])]
        snapshot = {"task": [a[0] for a in worker_actions],
                    "locations": [acting_farm["farmer"], *acting_farm["hands"]],
                    "inventory": {"seeds": state["seeds"], "shed": state["shed"]}}
        transitions = {key: previous is not None and snapshot[key] != previous[key]
                       for key in ("task", "locations", "inventory")}
        steps.append({"step": state["step"], "action": action, "capacity_usage": usage,
                      "capacity_limits": limits, "transitions": transitions})
        previous = snapshot
    return {"identity": {k: row[k] for k in ("opponent", "episode", "seed", "time", "seat")},
            "winner_trace_sha256": row["winner_trace_sha256"], "steps": steps,
            "transition_counts": {name: sum(step["transitions"][name] for step in steps)
                                  for name in ("task", "locations", "inventory")},
            "capacity_violations": violations}


def measure(policy: Path, config: dict[str, Any]) -> dict[str, Any]:
    split = validate_split(config)
    policy_sha = hashlib.sha256(policy.read_bytes()).hexdigest()
    provenance = {"policy_sha256": policy_sha, "fixture_sha256": canonical_sha256(config),
                  "winner_trace_hashes": sorted(row["winner_trace_sha256"] for w in WINDOWS for row in config[w])}
    if not split["passed"]:
        return {"passed": False, "split": split, "confirm": {"skipped": True, "reason": "screen isolation failed"},
                "provenance": provenance, "kaggle_submission": "NOT_PERFORMED"}
    module = load_agent(policy)
    panels: dict[str, Any] = {}
    for window in WINDOWS:
        if window == "confirm" and not panels["screen"]["passed"]:
            panels[window] = {"skipped": True, "reason": "screen gate failed"}
            break
        episodes = [_measure_episode(module, row) for row in config[window]]
        capacity = {name: sum(e["capacity_violations"][name] for e in episodes) for name in CAPACITIES}
        transitions = {name: sum(e["transition_counts"][name] for e in episodes)
                       for name in ("task", "locations", "inventory")}
        panels[window] = {"passed": all(value == 0 for value in capacity.values()), "episodes": episodes,
                          "both_seat_evidence": sorted({e["identity"]["seat"] for e in episodes}),
                          "transition_counts": transitions, "capacity_violations": capacity}
    passed = panels["screen"]["passed"] and panels.get("confirm", {}).get("passed", False)
    return {"issue": "SOT-2843", "passed": passed, "split": split, "screen": panels["screen"],
            "confirm": panels["confirm"], "provenance": provenance,
            "oracle_input_contract": "policy receives generated current runtime observation only; winner trace contributes immutable SHA-256 provenance only",
            "deterministic_report_sha256": canonical_sha256({"split": split, "panels": panels, "provenance": provenance}),
            "kaggle_submission": "NOT_PERFORMED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/multi_step_transition_oracle.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2842/SOT-2843-multi-step-transition-oracle.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.fixture.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "confirm_skipped": report["confirm"].get("skipped", False)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

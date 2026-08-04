#!/usr/bin/env python3
"""Deterministic, runtime-shaped screen/confirm Kaggriculture evaluator.

The simulator intentionally covers the crop/market subset used by this lineage.  Its
clock, observations, action timing, inventory flow, crop survival, and terminal
reward follow the public competition contract; unsupported animal/build actions are
accepted by the contract but remain silent no-ops.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import random
import subprocess
import sys
from math import ceil, log1p, sqrt
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

VALID_WORKER_ACTIONS = {
    "PASS", "NORTH", "SOUTH", "EAST", "WEST", "DIG", "PLANT", "WATER", "HARVEST",
    "PICKUP", "PLACE", "DROP", "FERTILIZE", "BUILD_COOP", "BUILD_PASTURE", "FEED",
    "COLLECT_FERTILIZER", "CARE",
}
VALID_MARKET_ACTIONS = {"SELL", "BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "HIRE", "BUY_LAND"}


@dataclass
class Metrics:
    reward: int = 0
    final_assets: int = 0
    profit: int = 0
    cultivated: int = 0
    harvested: int = 0
    invalid_actions: int = 0
    contract_violations: int = 0
    assignment_conflicts: int = 0
    leaderboard_proxy: int = 0

    def __add__(self, other: "Metrics") -> "Metrics":
        return Metrics(**{key: getattr(self, key) + getattr(other, key) for key in asdict(self)})


def load_agent(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"agent_{path.stem}_{id(path)}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load agent: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise ValueError(f"agent(obs) missing: {path}")
    return module


def _valid_worker_action(action: Any, crops: set[str]) -> bool:
    if not isinstance(action, list) or not action or action[0] not in VALID_WORKER_ACTIONS:
        return False
    if action[0] == "PLANT":
        return len(action) == 2 and action[1] in crops
    if action[0] in {"PICKUP", "PLACE"}:
        return len(action) in {2, 3} and isinstance(action[1], str) and (
            len(action) == 2 or (isinstance(action[2], int) and not isinstance(action[2], bool) and action[2] > 0)
        )
    return len(action) == 1


def _valid_action(result: Any, hand_count: int, crops: set[str], max_market_orders: int) -> bool:
    if not isinstance(result, dict) or set(result) != {"farmer", "hands", "market"}:
        return False
    if not _valid_worker_action(result["farmer"], crops):
        return False
    if not isinstance(result["hands"], list) or len(result["hands"]) != hand_count:
        return False
    if any(not _valid_worker_action(action, crops) for action in result["hands"]):
        return False
    return isinstance(result["market"], list) and len(result["market"]) <= max_market_orders and all(
        isinstance(action, list) and action and action[0] in VALID_MARKET_ACTIONS and
        ((action[0] in {"HIRE", "BUY_LAND"} and len(action) == 1) or
         (action[0] not in {"HIRE", "BUY_LAND"} and len(action) == 3 and isinstance(action[1], str) and
          isinstance(action[2], int) and not isinstance(action[2], bool) and action[2] > 0))
        for action in result["market"]
    )


def _hire_cost(hires_today: int) -> int:
    a, b = 1, 1
    for _ in range(hires_today):
        a, b = b, a + b
    return a


def _market_price(item: str, inventory: int, fixture: dict[str, Any]) -> int:
    """Return the public environment's rounded shared-market quote."""
    params = fixture["competitive_oracle"]["market_params"][item]
    base, anchor = float(params["base"]), int(params["initial_inventory"])
    throughput = max(1, int(params["throughput"]))
    delta = anchor - inventory
    side = "below" if delta >= 0 else "above"
    shape_name = params[f"{side}_func"]
    shape = {"linear": lambda x: x, "sqrt": sqrt, "log": log1p}[shape_name]
    target = float(params[f"{side}_target"])
    move = target * base * shape(abs(delta)) / shape(throughput)
    return max(1, round(base + move if delta >= 0 else base - move))


def run_competitive_market(fixture: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """Replay public multi-farm market orders with Kaggriculture lockstep ordering.

    The replay deliberately covers the coupling absent from ``run_episode``: all
    farms observe one market, orders at the same queue position receive the same
    pre-commit quote, and each unit changes the quote seen by later queue entries.
    Private sheds/seeds remain farm-local, while seeds are one shared pool for a
    farm's farmer and hands as required by the public runtime contract.
    """
    config = fixture["competitive_oracle"]
    products = tuple(config["market_params"])
    farms = copy.deepcopy(scenario["farms"])
    initial_market = {p: int(config["market_params"][p]["initial_inventory"]) for p in products}
    market = {"inventory": copy.deepcopy(initial_market)}
    market["prices"] = {p: _market_price(p, market["inventory"][p], fixture) for p in products}
    trace = []
    max_orders = int(fixture.get("submission_contract", {}).get("max_market_orders", 10))

    for turn, queues in enumerate(scenario["turns"]):
        queues = [list(queue[:max_orders]) for queue in queues]
        for order_index in range(max(map(len, queues), default=0)):
            active = []
            for player, queue in enumerate(queues):
                if order_index < len(queue):
                    op, item, amount = queue[order_index]
                    active.append({"player": player, "op": op, "item": item, "remaining": int(amount)})
            unit = 0
            while any(order["remaining"] > 0 for order in active):
                quoted = {}
                for order in active:
                    if order["remaining"] <= 0 or order["item"] not in products:
                        continue
                    item = order["item"]
                    inventory = market["inventory"][item]
                    quoted[order["player"]] = _market_price(
                        item, inventory - (1 if order["op"] == "BUY_PRODUCT" else 0), fixture
                    )
                commits = []
                for order in active:
                    player, op, item = order["player"], order["op"], order["item"]
                    if order["remaining"] <= 0 or player not in quoted:
                        continue
                    price, farm = quoted[player], farms[player]
                    private = farm["private"]
                    ok = False
                    if op == "SELL" and private["shed"].get(item, 0) > 0:
                        private["shed"][item] -= 1
                        farm["money"] += price
                        market["inventory"][item] += 1
                        ok = True
                    elif op == "BUY_PRODUCT" and market["inventory"][item] > 0 and farm["money"] >= price:
                        farm["money"] -= price
                        private["shed"][item] = private["shed"].get(item, 0) + 1
                        market["inventory"][item] -= 1
                        ok = True
                    elif op == "BUY_SEED" and item in private["seeds"]:
                        seed_price = int(config["seed_prices"][item])
                        if farm["money"] >= seed_price:
                            farm["money"] -= seed_price
                            private["seeds"][item] += 1
                            price, ok = seed_price, True
                    order["remaining"] -= 1
                    commits.append({"player": player, "op": op, "item": item, "price": price, "accepted": ok})
                trace.append({"turn": turn, "order_index": order_index, "unit": unit,
                              "pre_commit_quotes": quoted, "commits": commits})
                unit += 1
        market["prices"] = {p: _market_price(p, market["inventory"][p], fixture) for p in products}

    scores = [int(farm["money"]) for farm in farms]
    order = sorted(range(len(scores)), key=lambda player: (-scores[player], player))
    ranks = [order.index(player) + 1 for player in range(len(scores))]
    return {"name": scenario["name"], "farms": farms, "initial_market_inventory": initial_market,
            "shared_market": market,
            "scores": scores, "ranks": ranks, "relative_score": scores[0] - max(scores[1:]),
            "winner": order[0], "trace": trace}


def _competitive_gate(results: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "multiple_farms": all(len(result["farms"]) >= 2 for result in results),
        "relative_rank_matches_cash": all(
            result["winner"] == result["scores"].index(max(result["scores"])) for result in results
        ),
        "shared_market_mutates": all(
            result["shared_market"]["inventory"] != result["initial_market_inventory"] for result in results
        ),
        "lockstep_quotes": all(
            all(len(set(row["pre_commit_quotes"].values())) <= 1 for row in result["trace"])
            for result in results
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}


def _spawn_hand(positions: list[list[int]], quadrant: int) -> list[int]:
    """Choose the nearest free unlocked cell, with deterministic NWSE-style ties."""
    cells = sorted(((x, y) for y in range(quadrant) for x in range(quadrant)),
                   key=lambda value: (value[0] + value[1], value[1], value[0]))
    occupied = {tuple(position) for position in positions}
    return list(next((cell for cell in cells if cell not in occupied), cells[0]))


def bounded_rollout(
    observation: dict[str, Any],
    action_sequence: Sequence[dict[str, Any]],
    *,
    horizon: int,
    crop_specs: dict[str, dict[str, Any]],
    total_days: int,
    turns_per_day: int = 24,
) -> dict[str, Any]:
    """Deterministically score actions using only the supplied observation.

    This is deliberately a small limited-horizon search primitive rather than a
    second environment implementation.  Unknown future prices, weeds, and crop
    yields are never sampled or inferred: the current observed price is held
    constant, and crops only advance according to their public lifecycle fields.
    Callers can enumerate action sequences (or use them as MCTS leaves) without
    adding a runtime dependency.
    """
    if horizon < 0:
        raise ValueError("horizon must be non-negative")
    if total_days <= 0 or turns_per_day <= 0:
        raise ValueError("total_days and turns_per_day must be positive")
    obs = copy.deepcopy(observation)
    farm = obs["farms"][int(obs.get("player", 0))]
    private = obs.get("private", {})
    positions = [list(farm["farmer"]), *[list(value) for value in farm.get("hands", [])]]
    tiles = copy.deepcopy(farm["tiles"])
    seeds = {crop: int(value) for crop, value in private.get("seeds", {}).items()}
    shed = {crop: int(value) for crop, value in private.get("shed", {}).items()}
    inventories = [copy.deepcopy(value) for value in private.get("inventories", [])]
    inventories.extend({} for _ in range(max(0, len(positions) - len(inventories))))
    money = int(farm.get("money", 0))
    hires_today = int(farm.get("hires_today", 0))
    start_step = int(obs.get("step", int(obs.get("day", 0)) * turns_per_day + int(obs.get("hour", 0))))
    deadline_step = total_days * turns_per_day
    steps = min(horizon, len(action_sequence), max(0, deadline_step - start_step))
    prices = {crop: int(value) for crop, value in obs.get("market", {}).get("prices", {}).items()}
    invalid_actions = contract_violations = assignment_conflicts = 0
    max_market_orders = 10
    max_workers = 16

    for offset, result in enumerate(action_sequence[:steps]):
        day = (start_step + offset) // turns_per_day
        if not _valid_action(result, len(positions) - 1, set(crop_specs), max_market_orders):
            invalid_actions += 1
            contract_violations += 1
            continue
        for action in result["market"]:
            op = action[0]
            if op == "HIRE":
                cost = _hire_cost(hires_today)
                if money < cost or len(positions) >= max_workers:
                    invalid_actions += 1
                    continue
                money -= cost
                hires_today += 1
                positions.append(_spawn_hand(positions, len(tiles)))
                inventories.append({})
            elif op == "BUY_SEED" and action[1] in crop_specs:
                crop, amount = action[1], action[2]
                cost = int(crop_specs[crop].get("seed_price", 0)) * amount
                if money < cost:
                    invalid_actions += 1
                else:
                    money -= cost
                    seeds[crop] = seeds.get(crop, 0) + amount
            elif op == "SELL" and action[1] in crop_specs:
                crop, amount = action[1], action[2]
                if shed.get(crop, 0) < amount:
                    invalid_actions += 1
                else:
                    shed[crop] -= amount
                    money += prices.get(crop, 0) * amount
            else:
                invalid_actions += 1

        worker_actions = [result["farmer"], *result["hands"]]
        move_offsets = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
        destinations = []
        targets = []
        for position, action in zip(positions, worker_actions):
            if action[0] in move_offsets:
                dx, dy = move_offsets[action[0]]
                destinations.append((position[0] + dx, position[1] + dy))
            if action[0] in {"DIG", "PLANT", "WATER", "HARVEST"}:
                targets.append(tuple(position))
        assignment_conflicts += len(destinations) - len(set(destinations))
        duplicate_targets = len(targets) - len(set(targets))
        invalid_actions += duplicate_targets
        contract_violations += duplicate_targets
        for index, action in enumerate(worker_actions):
            positions[index], seeds, _, _, _, invalid = _apply_worker(
                action, positions[index], tiles, seeds, inventories[index], day, crop_specs
            )
            invalid_actions += invalid

    seed_value = sum(seeds.get(crop, 0) * int(spec.get("seed_price", 0)) for crop, spec in crop_specs.items())
    inventory_value = sum(
        amount * prices.get(crop, 0)
        for source in [shed, *inventories]
        for crop, amount in source.items()
    )
    remaining_steps = max(0, deadline_step - start_step - steps)
    # Terminal competition reward is cash only; before the deadline, liquid
    # observed inventory and unused seed at current prices for leaf ordering.
    score = money if remaining_steps == 0 else money + seed_value + inventory_value
    return {
        "cash": money,
        "seeds": seeds,
        "workers": positions,
        "tiles": tiles,
        "steps_simulated": steps,
        "deadline_step": deadline_step,
        "remaining_steps": remaining_steps,
        "invalid_actions": invalid_actions,
        "contract_violations": contract_violations,
        "assignment_conflicts": assignment_conflicts,
        "score": score - 1000 * invalid_actions,
    }


def _apply_worker(action, position, tiles, seeds, inventory, day, crops):
    x, y = position
    op = action[0]
    size = len(tiles)
    moves = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
    if op in moves:
        dx, dy = moves[op]
        nx, ny = x + dx, y + dy
        if 0 <= nx < size and 0 <= ny < size and tiles[ny][nx] != "LOCKED":
            return [nx, ny], seeds, 0, 0, 0, 0
        return position, seeds, 0, 0, 0, 1
    tile = tiles[y][x]
    if op == "PASS":
        return position, seeds, 0, 0, 0, 0
    if op == "DIG" and isinstance(tile, dict) and tile.get("kind") == "WEED":
        tiles[y][x] = None
        return position, seeds, 0, 0, 0, 0
    if op == "PLANT" and len(action) == 2 and action[1] in crops and tile is None and seeds.get(action[1], 0) > 0:
        crop = action[1]
        tiles[y][x] = {"kind": "PLANT", "crop": crop, "planted_day": day, "watered_today": False,
                       "consecutive_unwatered": 0, "yield_units": 0, "fertilized_until_day": -1}
        seeds[crop] -= 1
        return position, seeds, 1, 0, None, 0
    if op == "WATER" and isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile["watered_today"]:
        tile["watered_today"] = True
        return position, seeds, 0, 0, 0, 0
    if op == "HARVEST" and isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop = tile.get("crop")
        spec = crops.get(crop, {})
        maturity = int(spec.get("first_yield_day", spec.get("maturity_days", 2)))
        if day - tile["planted_day"] < maturity or int(tile.get("yield_units", 0)) <= 0:
            return position, seeds, 0, 0, None, 1
        amount = int(tile["yield_units"])
        inventory[crop] = inventory.get(crop, 0) + amount
        tiles[y][x] = None
        return position, seeds, 0, 1, (crop, amount), 0
    return position, seeds, 0, 0, None, 1


def run_episode(module: ModuleType, fixture: dict[str, Any], seed: int) -> Metrics:
    rng = random.Random(seed)
    days = int(fixture["days"])
    turns_per_day = int(fixture.get("turns_per_day", 12))
    size = int(fixture.get("board_size", 10))
    initial_money = int(fixture["initial_money"])
    crops = fixture.get("crops", {"WHEAT": {"seed_price": 10, "maturity_days": 2, "base_yield": 2,
                                               "yield_variance": 1, "prices": [fixture["sale_price"]]}})
    seeds = {crop: int(spec.get("initial_seeds", 0)) for crop, spec in crops.items()}
    if "initial_seeds" in fixture:
        seeds["WHEAT"] = int(fixture["initial_seeds"])
    money, shed = initial_money, {crop: 0 for crop in crops}
    quadrant = int(fixture.get("initial_quadrant_size", size // 2))
    tiles = [[None if x < quadrant and y < quadrant else "LOCKED" for x in range(size)] for y in range(size)]
    for x, y in fixture.get("initial_weeds", []):
        if 0 <= x < quadrant and 0 <= y < quadrant:
            tiles[y][x] = {"kind": "WEED"}
    metrics = Metrics()
    contract = fixture.get("submission_contract", {})
    max_market_orders = int(contract.get("max_market_orders", 10))
    max_workers = int(contract.get("max_workers", 16))
    invalid_penalty = int(fixture.get("oracle", {}).get("invalid_action_penalty", 1000))

    for day in range(days):
        initial_hands = max(0, int(fixture.get("initial_hands", 0)))
        positions = [[0, 0]]
        while len(positions) <= initial_hands and len(positions) < max_workers:
            positions.append(_spawn_hand(positions, quadrant))
        inventories = [{} for _ in positions]
        hires_today = 0
        for hour in range(turns_per_day):
            prices = {crop: int(spec.get("prices", [spec.get("fallback_price", 0)])[day % len(spec.get("prices", [0]))])
                      for crop, spec in crops.items()}
            obs = {
                "player": 0, "step": day * turns_per_day + hour, "day": day, "hour": hour,
                "farms": [{"money": money, "farmer": positions[0], "hands": positions[1:],
                           "hires_today": hires_today, "unlocked_quadrants": ["NW"], "tiles": copy.deepcopy(tiles)}],
                "private": {"shed": copy.deepcopy(shed), "seeds": copy.deepcopy(seeds),
                            "inventories": [copy.deepcopy(value) for value in inventories]},
                "market": {"inventory": {crop: 10000 for crop in crops}, "prices": prices},
                "town": {"unlocked_shops": []},
            }
            try:
                result = module.agent(copy.deepcopy(obs))
            except Exception:
                metrics.invalid_actions += 1
                continue
            if not _valid_action(result, len(positions) - 1, set(crops), max_market_orders):
                metrics.invalid_actions += 1
                metrics.contract_violations += 1
                continue
            for action in result["market"]:
                if action[0] == "HIRE" and len(action) == 1:
                    cost = _hire_cost(hires_today)
                    if money >= cost and len(positions) < max_workers:
                        money -= cost
                        hires_today += 1
                        positions.append(_spawn_hand(positions, quadrant))
                        inventories.append({})
                    else:
                        metrics.invalid_actions += 1
                elif len(action) == 3 and isinstance(action[2], int) and action[2] > 0:
                    amount = action[2]
                    crop = action[1]
                    if action[0] == "BUY_SEED" and crop in crops and money >= int(crops[crop]["seed_price"]) * amount:
                        money -= int(crops[crop]["seed_price"]) * amount
                        seeds[crop] += amount
                    elif action[0] == "SELL" and crop in crops and shed[crop] >= amount:
                        money += prices[crop] * amount
                        shed[crop] -= amount
                    else:
                        metrics.invalid_actions += 1
                else:
                    metrics.invalid_actions += 1
            worker_actions = [result["farmer"]] + result["hands"]
            projected = []
            move_offsets = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
            for position, action in zip(positions, worker_actions):
                dx, dy = move_offsets.get(action[0], (0, 0))
                projected.append((position[0] + dx, position[1] + dy))
            moving_destinations = [destination for destination, action in zip(projected, worker_actions)
                                   if action[0] in move_offsets]
            metrics.assignment_conflicts += len(moving_destinations) - len(set(moving_destinations))
            targets = []
            for index, action in enumerate(worker_actions):
                if action[0] in {"DIG", "PLANT", "WATER", "HARVEST"}:
                    targets.append(tuple(positions[index]))
            if len(targets) != len(set(targets)):
                metrics.invalid_actions += len(targets) - len(set(targets))
                metrics.contract_violations += len(targets) - len(set(targets))
            for index, action in enumerate(worker_actions):
                positions[index], seeds, cultivated, harvested, produced, invalid = _apply_worker(
                    action, positions[index], tiles, seeds, inventories[index], day, crops
                )
                metrics.cultivated += cultivated
                metrics.harvested += harvested
                metrics.invalid_actions += invalid
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    spec = crops[tile["crop"]]
                    next_age = day + 1 - int(tile["planted_day"])
                    if next_age >= int(spec.get("first_yield_day", spec.get("maturity_days", 2))):
                        tile["yield_units"] = max(1, int(tile.get("yield_units", 0)))
                    if tile.get("watered_today"):
                        age = day - int(tile["planted_day"])
                        bonus_start = (int(spec.get("max_yield_day", 4)) + 1) // 2
                        if age >= bonus_start:
                            tile["yield_units"] = min(int(spec.get("max_yield", 6)),
                                                      int(tile.get("yield_units", 1)) + 1)
                        tile["consecutive_unwatered"] = 0
                    else:
                        tile["consecutive_unwatered"] = int(tile.get("consecutive_unwatered", 0)) + 1
                    tile["watered_today"] = False
                    if tile["consecutive_unwatered"] >= 2:
                        tile.clear()
                        tile.update({"kind": "WEED"})
        # Runtime workers carry harvested goods; the end-of-day refresh drops them
        # into the capped shed before hands disappear.
        capacity = int(fixture.get("shed_capacity", 100))
        for inventory in inventories:
            for crop, amount in inventory.items():
                room = max(0, capacity - sum(shed.values()))
                shed[crop] += min(amount, room)
        if rng.random() < 0.2:
            empties = [(x, y) for y, row in enumerate(tiles) for x, tile in enumerate(row) if tile is None]
            if empties:
                x, y = rng.choice(empties)
                tiles[y][x] = {"kind": "WEED"}

    metrics.reward = money
    metrics.final_assets = money
    metrics.profit = metrics.final_assets - initial_money
    metrics.leaderboard_proxy = metrics.reward - invalid_penalty * metrics.invalid_actions
    return metrics


def evaluate(module: ModuleType, fixture: dict[str, Any], seeds: list[int]) -> dict[str, Any]:
    episodes = [asdict(run_episode(module, fixture, seed)) | {"seed": seed} for seed in seeds]
    totals = Metrics()
    for episode in episodes:
        totals += Metrics(**{key: episode[key] for key in asdict(Metrics())})
    averages = {key: getattr(totals, key) / len(episodes) for key in asdict(totals)}
    return {"seeds": seeds, "episodes": episodes, "mean": averages}


def _merge_fixture(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_fixture(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def evaluate_scenarios(module: ModuleType, fixture: dict[str, Any], scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate named distribution shifts and report tail and worst-case metrics."""
    scenario_results, episodes = {}, []
    for scenario in scenarios:
        result = evaluate(module, _merge_fixture(fixture, scenario.get("overrides", {})), scenario["seeds"])
        scenario_results[scenario["name"]] = result
        episodes.extend({**episode, "scenario": scenario["name"]} for episode in result["episodes"])
    metric_names = tuple(asdict(Metrics()))
    mean = {metric: sum(float(episode[metric]) for episode in episodes) / len(episodes) for metric in metric_names}
    lower_quantile, worst = {}, {}
    for metric in metric_names:
        values = sorted(float(episode[metric]) for episode in episodes)
        lower_quantile[metric] = values[max(0, ceil(0.2 * len(values)) - 1)]
        worst[metric] = max(values) if metric in {"invalid_actions", "contract_violations", "assignment_conflicts"} else min(values)
    return {"scenario_names": [scenario["name"] for scenario in scenarios], "scenarios": scenario_results,
            "episodes": episodes, "mean": mean, "lower_quantile": lower_quantile, "worst": worst}


def compare(champion, candidate, thresholds):
    reasons = []
    for metric in ("final_assets", "profit", "cultivated", "harvested"):
        minimum = float(thresholds.get(f"min_{metric}_ratio", 1.0))
        base = champion["mean"][metric]
        ratio = (1.0 if candidate["mean"][metric] == 0 else float("inf")) if base == 0 else candidate["mean"][metric] / base
        if ratio < minimum:
            reasons.append(f"{metric} ratio {ratio:.3f} < {minimum:.3f}")
    max_invalid = min(int(thresholds.get("max_invalid_actions", 0)), int(champion["mean"]["invalid_actions"]))
    if candidate["mean"]["invalid_actions"] > max_invalid:
        reasons.append(f"invalid_actions {candidate['mean']['invalid_actions']:.3f} > {max_invalid}")
    if candidate["mean"].get("contract_violations", 0) > champion["mean"].get("contract_violations", 0):
        reasons.append("submission contract violations increased")
    if candidate["mean"].get("assignment_conflicts", 0) > champion["mean"].get("assignment_conflicts", 0):
        reasons.append("worker movement conflicts increased")
    return not reasons, reasons


def compare_distribution(champion, candidate, thresholds):
    reasons = []
    for statistic in ("lower_quantile", "worst"):
        for metric in ("final_assets", "profit"):
            minimum = float(thresholds.get(f"min_{statistic}_{metric}_ratio", 1.0))
            base = champion[statistic][metric]
            ratio = (1.0 if candidate[statistic][metric] == 0 else float("inf")) if base == 0 else candidate[statistic][metric] / base
            if ratio < minimum:
                reasons.append(f"{statistic} {metric} ratio {ratio:.3f} < {minimum:.3f}")
    for metric in ("invalid_actions", "contract_violations"):
        if candidate["worst"][metric] > champion["worst"][metric]:
            reasons.append(f"worst {metric} increased")
    if thresholds.get("require_tail_or_worst_improvement"):
        improved = any(
            candidate[statistic][metric] > champion[statistic][metric]
            for statistic in ("lower_quantile", "worst")
            for metric in ("final_assets", "profit")
        )
        if not improved:
            reasons.append("no strict lower-tail or worst-case improvement")
    return not reasons, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    champion, candidate = load_agent(args.champion), load_agent(args.candidate)
    # The frozen policy baseline shares the compact submission source, so isolate
    # this experiment axis explicitly instead of attributing unrelated constants.
    if hasattr(champion, "ROBUST_ONLINE_PLANNER"):
        champion.ROBUST_ONLINE_PLANNER = False
    if hasattr(candidate, "ROBUST_ONLINE_PLANNER"):
        candidate.ROBUST_ONLINE_PLANNER = True
    screen_scenarios = fixture.get("screen_scenarios", [{"name": "baseline", "seeds": fixture["screen_seeds"]}])
    confirm_scenarios = fixture.get("confirm_scenarios", [{"name": "baseline", "seeds": fixture["confirm_seeds"]}])
    champion_screen = evaluate_scenarios(champion, fixture, screen_scenarios)
    variants = {}
    strategies = fixture.get("strategy_candidates", [{"crop": "BEST_RETURN", "sell": "PRICE_AWARE"}])
    for strategy in strategies:
        candidate.CROP_STRATEGY = strategy["crop"]
        candidate.SELL_STRATEGY = strategy["sell"]
        key = f"{strategy['crop']}:{strategy['sell']}"
        variants[key] = evaluate_scenarios(candidate, fixture, screen_scenarios)
    eligible = [(value["mean"]["final_assets"], -value["mean"]["invalid_actions"], key)
                for key, value in variants.items() if value["mean"]["invalid_actions"] <= champion_screen["mean"]["invalid_actions"]]
    selected = max(eligible)[2] if eligible else sorted(variants)[0]
    selected_crop, selected_sell = selected.split(":", 1)
    candidate.CROP_STRATEGY, candidate.SELL_STRATEGY = selected_crop, selected_sell
    result = {"fixture": str(args.fixture),
              "provenance": {"champion": str(args.champion), "candidate": str(args.candidate),
                             "submission_builder": "scripts/build_submission.sh",
                             "submission_artifact": "submission.tar.gz"},
              "thresholds": fixture["thresholds"],
              "oracle": fixture.get("oracle", {}),
              "robust_online_planner": {
                  "enabled_for_candidate": bool(getattr(candidate, "ROBUST_ONLINE_PLANNER", False)),
                  "enabled_for_champion": bool(getattr(champion, "ROBUST_ONLINE_PLANNER", False)),
                  "information_boundary": "bounded public price, crop-yield, and weed observations only",
                  "history_limit": int(getattr(candidate, "HISTORY_LIMIT", 0)),
                  "scenario_count": 3,
                  "objective": "mean of two worst scenario returns (CVaR proxy)",
                  "fixed_screen_then_independent_confirm": True,
              },
              "submission_contract": fixture.get("submission_contract", {}), "screen": {
        "champion": champion_screen, "strategy_variants": variants, "selected_strategy": selected,
        "candidate": variants[str(selected)]}}
    if "competitive_oracle" in fixture:
        competitive_screen = [run_competitive_market(fixture, value)
                              for value in fixture["competitive_oracle"]["screen"]]
        result["competitive_oracle"] = {
            "contract": fixture["competitive_oracle"]["contract"],
            "screen": {"scenarios": competitive_screen, **_competitive_gate(competitive_screen)},
        }
        if result["competitive_oracle"]["screen"]["passed"]:
            competitive_confirm = [run_competitive_market(fixture, value)
                                   for value in fixture["competitive_oracle"]["confirm"]]
            result["competitive_oracle"]["confirm"] = {
                "scenarios": competitive_confirm, **_competitive_gate(competitive_confirm)
            }
        else:
            result["competitive_oracle"]["confirm"] = {
                "skipped": True, "reason": "competitive oracle did not pass fixed-seed screen"
            }
    if "rollout" in fixture:
        rollout = fixture["rollout"]
        rollout_kwargs = {
            "horizon": int(rollout["horizon"]),
            "crop_specs": fixture["crops"],
            "total_days": int(fixture["days"]),
            "turns_per_day": int(fixture.get("turns_per_day", 24)),
        }
        result["rollout"] = {
            "information_boundary": "supplied observation only; current prices held constant",
            "champion": bounded_rollout(rollout["observation"], rollout["champion"], **rollout_kwargs),
            "candidate": bounded_rollout(rollout["observation"], rollout["candidate"], **rollout_kwargs),
        }
    mean_passed, reasons = compare(champion_screen, variants[str(selected)], fixture["thresholds"])
    tail_passed, tail_reasons = compare_distribution(champion_screen, variants[str(selected)], fixture["thresholds"])
    passed = mean_passed and tail_passed
    reasons.extend(tail_reasons)
    result["screen"].update({"passed": passed, "reasons": reasons})
    if passed:
        result["confirm"] = {"champion": evaluate_scenarios(champion, fixture, confirm_scenarios),
                             "candidate": evaluate_scenarios(candidate, fixture, confirm_scenarios),
                             "selected_strategy": selected}
        mean_confirmed, reasons = compare(result["confirm"]["champion"], result["confirm"]["candidate"], fixture["thresholds"])
        tail_confirmed, tail_reasons = compare_distribution(result["confirm"]["champion"], result["confirm"]["candidate"], fixture["thresholds"])
        confirmed = mean_confirmed and tail_confirmed
        reasons.extend(tail_reasons)
        result["confirm"].update({"passed": confirmed, "reasons": reasons})
    else:
        result["confirm"] = {"skipped": True, "reason": "candidate did not pass screen"}
        confirmed = False
    result["decision"] = "PROMOTE" if passed and confirmed else "REJECT"
    if result["decision"] == "PROMOTE":
        check = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")), str(args.candidate)], capture_output=True, text=True)
        result["exec_compatibility"] = {"passed": check.returncode == 0, "output": (check.stdout + check.stderr).strip()}
        result["next_action"] = "kaggle_validation" if check.returncode == 0 else "fix_exec_compatibility"
    else:
        result["exec_compatibility"] = {"skipped": True, "reason": "candidate rejected"}
        result["next_action"] = "revert_candidate_keep_measurement"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"evaluation: {result['decision']} ({args.output})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

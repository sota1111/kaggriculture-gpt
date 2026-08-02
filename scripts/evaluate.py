#!/usr/bin/env python3
"""Deterministic screen/confirm evaluator with routing and farm-hand simulation."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import random
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

VALID_WORKER_ACTIONS = {"PASS", "NORTH", "SOUTH", "EAST", "WEST", "DIG", "PLANT", "WATER", "HARVEST"}
VALID_MARKET_ACTIONS = {"SELL", "BUY_SEED", "HIRE"}


@dataclass
class Metrics:
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
    return len(action) == 2 and action[1] in crops if action[0] == "PLANT" else len(action) == 1


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
        ((action[0] == "HIRE" and len(action) == 1) or
         (action[0] != "HIRE" and len(action) == 3 and action[1] in crops and
          isinstance(action[2], int) and not isinstance(action[2], bool) and action[2] > 0))
        for action in result["market"]
    )


def _hire_cost(hires_today: int) -> int:
    a, b = 1, 1
    for _ in range(hires_today):
        a, b = b, a + b
    return a


def _apply_worker(action, position, tiles, seeds, day, rng, crops):
    x, y = position
    op = action[0]
    size = len(tiles)
    moves = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
    if op in moves:
        dx, dy = moves[op]
        nx, ny = x + dx, y + dy
        if 0 <= nx < size and 0 <= ny < size:
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
        tiles[y][x] = {"kind": "PLANT", "crop": crop, "planted_day": day, "watered_today": False, "yield_units": 0}
        seeds[crop] -= 1
        return position, seeds, 1, 0, None, 0
    if op == "WATER" and isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile["watered_today"]:
        tile["watered_today"] = True
        return position, seeds, 0, 0, 0, 0
    if op == "HARVEST" and isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop = tile.get("crop")
        spec = crops.get(crop, {})
        maturity = int(spec.get("maturity_days", 2))
        if day - tile["planted_day"] < maturity:
            return position, seeds, 0, 0, None, 1
        amount = int(spec.get("base_yield", 2)) + rng.randint(0, int(spec.get("yield_variance", 1)))
        tiles[y][x] = None
        return position, seeds, 0, 1, (crop, amount), 0
    return position, seeds, 0, 0, None, 1


def run_episode(module: ModuleType, fixture: dict[str, Any], seed: int) -> Metrics:
    rng = random.Random(seed)
    days = int(fixture["days"])
    turns_per_day = int(fixture.get("turns_per_day", 12))
    size = int(fixture.get("board_size", 5))
    initial_money = int(fixture["initial_money"])
    crops = fixture.get("crops", {"WHEAT": {"seed_price": 10, "maturity_days": 2, "base_yield": 2,
                                               "yield_variance": 1, "prices": [fixture["sale_price"]]}})
    seeds = {crop: int(spec.get("initial_seeds", 0)) for crop, spec in crops.items()}
    if "initial_seeds" in fixture:
        seeds["WHEAT"] = int(fixture["initial_seeds"])
    money, shed = initial_money, {crop: 0 for crop in crops}
    tiles = [[None for _ in range(size)] for _ in range(size)]
    metrics = Metrics()
    contract = fixture.get("submission_contract", {})
    max_market_orders = int(contract.get("max_market_orders", 10))
    max_workers = int(contract.get("max_workers", 16))
    invalid_penalty = int(fixture.get("oracle", {}).get("invalid_action_penalty", 1000))

    for day in range(days):
        positions = [[0, 0]]
        hires_today = 0
        for hour in range(turns_per_day):
            prices = {crop: int(spec.get("prices", [spec.get("fallback_price", 0)])[day % len(spec.get("prices", [0]))])
                      for crop, spec in crops.items()}
            public_crops = {crop: {"seed_price": spec["seed_price"], "maturity_days": spec["maturity_days"],
                                    "expected_yield": spec["base_yield"] + spec.get("yield_variance", 0) / 2,
                                    "fallback_price": spec.get("fallback_price", prices[crop]),
                                    "sell_above": spec.get("sell_above", spec.get("fallback_price", prices[crop])),
                                    "price_forecast": list(spec.get("prices", []))}
                            for crop, spec in crops.items()}
            obs = {
                "player": 0, "step": day * turns_per_day + hour, "day": day, "hour": hour,
                "turns_per_day": turns_per_day, "total_days": days,
                "farms": [{"money": money, "farmer": positions[0], "hands": positions[1:],
                           "hires_today": hires_today, "unlocked_quadrants": ["NW"], "tiles": copy.deepcopy(tiles)}],
                "private": {"shed": copy.deepcopy(shed), "seeds": copy.deepcopy(seeds),
                            "inventories": [[] for _ in positions]},
                "market": {"inventory": {crop: 10000 for crop in crops}, "prices": prices},
                "crops": public_crops,
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
                        positions.append([0, 0])
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
                    action, positions[index], tiles, seeds, day, rng, crops
                )
                metrics.cultivated += cultivated
                metrics.harvested += harvested
                if produced:
                    shed[produced[0]] += produced[1]
                metrics.invalid_actions += invalid
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    tile["watered_today"] = False
        if rng.random() < 0.2:
            empties = [(x, y) for y, row in enumerate(tiles) for x, tile in enumerate(row) if tile is None]
            if empties:
                x, y = rng.choice(empties)
                tiles[y][x] = {"kind": "WEED"}

    final_prices = {crop: int(spec.get("prices", [spec.get("fallback_price", 0)])[-1]) for crop, spec in crops.items()}
    metrics.final_assets = money + sum(shed[crop] * final_prices[crop] for crop in crops) + sum(
        seeds[crop] * int(crops[crop]["seed_price"]) for crop in crops)
    metrics.profit = metrics.final_assets - initial_money
    metrics.leaderboard_proxy = metrics.final_assets - invalid_penalty * metrics.invalid_actions
    return metrics


def evaluate(module: ModuleType, fixture: dict[str, Any], seeds: list[int]) -> dict[str, Any]:
    episodes = [asdict(run_episode(module, fixture, seed)) | {"seed": seed} for seed in seeds]
    totals = Metrics()
    for episode in episodes:
        totals += Metrics(**{key: episode[key] for key in asdict(Metrics())})
    averages = {key: getattr(totals, key) / len(episodes) for key in asdict(totals)}
    return {"seeds": seeds, "episodes": episodes, "mean": averages}


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    champion, candidate = load_agent(args.champion), load_agent(args.candidate)
    champion_screen = evaluate(champion, fixture, fixture["screen_seeds"])
    variants = {}
    strategies = fixture.get("strategy_candidates", [{"crop": "BEST_RETURN", "sell": "PRICE_AWARE"}])
    for strategy in strategies:
        candidate.CROP_STRATEGY = strategy["crop"]
        candidate.SELL_STRATEGY = strategy["sell"]
        key = f"{strategy['crop']}:{strategy['sell']}"
        variants[key] = evaluate(candidate, fixture, fixture["screen_seeds"])
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
              "submission_contract": fixture.get("submission_contract", {}), "screen": {
        "champion": champion_screen, "strategy_variants": variants, "selected_strategy": selected,
        "candidate": variants[str(selected)]}}
    passed, reasons = compare(champion_screen, variants[str(selected)], fixture["thresholds"])
    result["screen"].update({"passed": passed, "reasons": reasons})
    if passed:
        result["confirm"] = {"champion": evaluate(champion, fixture, fixture["confirm_seeds"]),
                             "candidate": evaluate(candidate, fixture, fixture["confirm_seeds"]),
                             "selected_strategy": selected}
        confirmed, reasons = compare(result["confirm"]["champion"], result["confirm"]["candidate"], fixture["thresholds"])
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

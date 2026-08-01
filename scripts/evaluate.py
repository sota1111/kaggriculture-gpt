#!/usr/bin/env python3
"""Deterministic offline screen/confirm evaluator for Kaggriculture agents."""

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


VALID_FARMER_ACTIONS = {"PASS", "PLANT", "WATER", "HARVEST"}
VALID_MARKET_ACTIONS = {"SELL", "BUY_SEED"}


@dataclass
class Metrics:
    final_assets: int = 0
    profit: int = 0
    cultivated: int = 0
    harvested: int = 0
    invalid_actions: int = 0

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


def _valid_action(result: Any, hand_count: int) -> bool:
    if not isinstance(result, dict) or set(result) != {"farmer", "hands", "market"}:
        return False
    farmer = result["farmer"]
    hands = result["hands"]
    market = result["market"]
    if not isinstance(farmer, list) or not farmer or farmer[0] not in VALID_FARMER_ACTIONS:
        return False
    if not isinstance(hands, list) or len(hands) != hand_count:
        return False
    if any(not isinstance(action, list) or not action or action[0] != "PASS" for action in hands):
        return False
    return isinstance(market, list) and all(
        isinstance(action, list) and action and action[0] in VALID_MARKET_ACTIONS for action in market
    )


def run_episode(module: ModuleType, fixture: dict[str, Any], seed: int) -> Metrics:
    """Run the small deterministic contract simulator used for regression screening."""
    rng = random.Random(seed)
    days = int(fixture["days"])
    initial_money = int(fixture["initial_money"])
    money = initial_money
    seeds = int(fixture["initial_seeds"])
    shed = 0
    tile = None
    metrics = Metrics()

    for day in range(days):
        obs = {
            "player": 0,
            "day": day,
            "farms": [{"money": money, "farmer": [0, 0], "hands": [], "tiles": [[copy.deepcopy(tile)]]}],
            "private": {"shed": {"WHEAT": shed}, "seeds": {"WHEAT": seeds}, "inventories": [[]]},
        }
        try:
            result = module.agent(copy.deepcopy(obs))
        except Exception:
            metrics.invalid_actions += 1
            continue
        if not _valid_action(result, 0):
            metrics.invalid_actions += 1
            continue

        for action in result["market"]:
            kind = action[0]
            amount = action[2] if len(action) == 3 and isinstance(action[2], int) and action[2] > 0 else 0
            if kind == "BUY_SEED" and len(action) == 3 and action[1] == "WHEAT" and money >= 10 * amount:
                money -= 10 * amount
                seeds += amount
            elif kind == "SELL" and len(action) == 3 and action[1] == "WHEAT" and shed >= amount:
                money += int(fixture["sale_price"]) * amount
                shed -= amount
            else:
                metrics.invalid_actions += 1

        action = result["farmer"][0]
        if action == "PLANT" and tile is None and seeds > 0:
            seeds -= 1
            tile = {"kind": "PLANT", "planted_day": day, "watered_today": False}
            metrics.cultivated += 1
        elif action == "WATER" and tile is not None and not tile["watered_today"]:
            tile["watered_today"] = True
        elif action == "HARVEST" and tile is not None and day - tile["planted_day"] >= 2:
            shed += int(fixture["base_yield"]) + rng.randint(0, int(fixture["yield_variance"]))
            tile = None
            metrics.harvested += 1
        elif action != "PASS":
            metrics.invalid_actions += 1
        if tile is not None:
            tile["watered_today"] = False

    metrics.final_assets = money + shed * int(fixture["sale_price"]) + seeds * 10
    metrics.profit = metrics.final_assets - initial_money
    return metrics


def evaluate(module: ModuleType, fixture: dict[str, Any], seeds: list[int]) -> dict[str, Any]:
    episodes = [asdict(run_episode(module, fixture, seed)) | {"seed": seed} for seed in seeds]
    totals = Metrics()
    for episode in episodes:
        totals += Metrics(**{key: episode[key] for key in asdict(Metrics())})
    averages = {key: getattr(totals, key) / len(episodes) for key in asdict(totals)}
    return {"seeds": seeds, "episodes": episodes, "mean": averages}


def compare(champion: dict[str, Any], candidate: dict[str, Any], thresholds: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    for metric in ("final_assets", "profit", "cultivated", "harvested"):
        minimum = float(thresholds.get(f"min_{metric}_ratio", 1.0))
        base = champion["mean"][metric]
        if base == 0:
            ratio = 1.0 if candidate["mean"][metric] == 0 else float("inf")
        else:
            ratio = candidate["mean"][metric] / base
        if ratio < minimum:
            reasons.append(f"{metric} ratio {ratio:.3f} < {minimum:.3f}")
    max_invalid = int(thresholds.get("max_invalid_actions", 0))
    if candidate["mean"]["invalid_actions"] > max_invalid:
        reasons.append(f"invalid_actions {candidate['mean']['invalid_actions']:.3f} > {max_invalid}")
    return not reasons, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    champion = load_agent(args.champion)
    candidate = load_agent(args.candidate)
    result: dict[str, Any] = {"fixture": str(args.fixture), "thresholds": fixture["thresholds"]}
    result["screen"] = {
        "champion": evaluate(champion, fixture, fixture["screen_seeds"]),
        "candidate": evaluate(candidate, fixture, fixture["screen_seeds"]),
    }
    passed, reasons = compare(result["screen"]["champion"], result["screen"]["candidate"], fixture["thresholds"])
    result["screen"]["passed"] = passed
    result["screen"]["reasons"] = reasons
    if passed:
        result["confirm"] = {
            "champion": evaluate(champion, fixture, fixture["confirm_seeds"]),
            "candidate": evaluate(candidate, fixture, fixture["confirm_seeds"]),
        }
        confirmed, reasons = compare(result["confirm"]["champion"], result["confirm"]["candidate"], fixture["thresholds"])
        result["confirm"]["passed"] = confirmed
        result["confirm"]["reasons"] = reasons
    else:
        result["confirm"] = {"skipped": True, "reason": "candidate did not pass screen"}
        confirmed = False
    result["decision"] = "PROMOTE" if passed and confirmed else "REJECT"
    if result["decision"] == "PROMOTE":
        validator = Path(__file__).with_name("validate_submission.py")
        check = subprocess.run(
            [sys.executable, str(validator), str(args.candidate)],
            capture_output=True,
            text=True,
            check=False,
        )
        result["exec_compatibility"] = {
            "passed": check.returncode == 0,
            "command": f"{sys.executable} {validator} {args.candidate}",
            "output": (check.stdout + check.stderr).strip(),
        }
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

"""Default-off adversarial shared-market policy using public state only."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("relative_margin_champion", ROOT / "main.py")
_CHAMPION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CHAMPION)

MAX_ORDERS = 10
MIN_CASH_RUNWAY = 250
DENIAL_WEIGHT = 1.25


def _tiles(farm):
    for row in farm.get("tiles", ()):
        for tile in row:
            if isinstance(tile, dict):
                yield tile


def public_opponent_model(obs):
    """Estimate rival supply pressure without private state or future values."""
    player = int(obs.get("player", 0))
    crops = {}
    hands = animals = 0
    for index, farm in enumerate(obs.get("farms", ())):
        if index == player:
            continue
        hands += len(farm.get("hands", ()))
        for tile in _tiles(farm):
            kind = str(tile.get("kind", "")).upper()
            crop = str(tile.get("crop", tile.get("product", ""))).upper()
            if kind == "PLANT" and crop:
                crops[crop] = crops.get(crop, 0) + 1
            elif kind == "ANIMAL":
                animals += 1
    demand = obs.get("town", {}).get("demand", {})
    if not isinstance(demand, dict):
        demand = {}
    market = obs.get("market", {})
    return {
        "crop_footprint": crops,
        "hands": hands,
        "animals": animals,
        "town_demand": {str(k).upper(): max(0, int(v)) for k, v in demand.items()},
        "inventory": {str(k).upper(): max(0, int(v)) for k, v in market.get("inventory", {}).items()},
        "prices": {str(k).upper(): max(0, int(v)) for k, v in market.get("prices", {}).items()},
    }


def _cash(obs):
    player = int(obs.get("player", 0))
    farms = obs.get("farms", ())
    if 0 <= player < len(farms):
        return max(0, int(farms[player].get("cash", farms[player].get("bank", 0))))
    return 0


def _own_stock(obs, crop):
    player = int(obs.get("player", 0))
    farms = obs.get("farms", ())
    if not 0 <= player < len(farms):
        return 0
    inventory = farms[player].get("inventory", farms[player].get("shed", {}))
    return max(0, int(inventory.get(crop, 0))) if isinstance(inventory, dict) else 0


def counterfactual_market_plans(obs, baseline):
    """Return a bounded finite plan set with explicit relative-margin scores."""
    model = public_opponent_model(obs)
    cash = _cash(obs)
    plans = [{"name": "champion", "score": 0.0, "crop": None,
              "market": list(baseline.get("market", ())), "reason": "hedge"}]
    for crop, price in sorted(model["prices"].items()):
        if price <= 0:
            continue
        rival_supply = model["crop_footprint"].get(crop, 0)
        demand = model["town_demand"].get(crop, 0)
        shared = model["inventory"].get(crop, 10000)
        scarcity = max(0.0, (10000 - min(10000, shared)) / 10000)

        # Buy at most two public units when rival production is feed/demand
        # exposed.  Cash runway and the global order cap are hard constraints.
        quantity = min(2, max(0, (cash - MIN_CASH_RUNWAY) // price))
        denial_value = quantity * price * (0.35 * rival_supply + 0.25 * demand + scarcity)
        own_cost = quantity * price
        buy_score = DENIAL_WEIGHT * denial_value - own_cost
        if quantity and buy_score > 0:
            orders = [["BUY_PRODUCT", crop, int(quantity)], *baseline.get("market", ())]
            plans.append({"name": "buy_denial", "score": buy_score, "crop": crop,
                          "market": orders[:MAX_ORDERS], "reason": "rival_supply_and_scarcity"})

        # Selling competes with rival supply.  Prefer a demanded crop with low
        # rival footprint; holding is represented by the untouched baseline.
        stock = _own_stock(obs, crop)
        sell_qty = min(3, stock)
        sale_value = sell_qty * price
        price_impact = sell_qty * price * (rival_supply / max(1, shared))
        sell_score = sale_value - DENIAL_WEIGHT * price_impact + demand * price * 0.1
        if sell_qty and sell_score > 0:
            without_crop_sales = [o for o in baseline.get("market", ())
                                  if not (len(o) > 1 and o[0] == "SELL" and o[1] == crop)]
            plans.append({"name": "timed_sale", "score": sell_score, "crop": crop,
                          "market": [["SELL", crop, sell_qty], *without_crop_sales][:MAX_ORDERS],
                          "reason": "demand_minus_rival_supply"})

        # Production mix is chosen in the same objective, favoring demand gaps
        # and avoiding a rival-saturated crop.
        production_score = price * (1 + demand) / (1 + rival_supply) + price * scarcity
        plans.append({"name": "production_mix", "score": production_score, "crop": crop,
                      "market": list(baseline.get("market", ()))[:MAX_ORDERS],
                      "reason": "public_relative_margin_gap"})
    return plans


def choose_relative_margin_plan(obs, baseline):
    plans = counterfactual_market_plans(obs, baseline)
    return max(plans, key=lambda p: (p["score"], p["name"], p.get("crop") or ""))


def agent(obs):
    baseline = _CHAMPION.agent(obs)
    plan = choose_relative_margin_plan(obs, baseline)
    farmer = list(baseline.get("farmer", ["PASS"]))
    hands = [list(action) for action in baseline.get("hands", ())]
    if plan["name"] == "production_mix" and plan["crop"]:
        if farmer and farmer[0] == "PLANT":
            farmer = ["PLANT", plan["crop"]]
        hands = [["PLANT", plan["crop"]] if action and action[0] == "PLANT" else action
                 for action in hands]
    return {"farmer": farmer, "hands": hands, "market": plan["market"][:MAX_ORDERS]}

"""Leak-free engine-identity attribution for Kaggriculture trajectories."""
from __future__ import annotations

from collections import Counter
from typing import Any

from scripts.evaluation.economic_oracle import EngineDriftError

IDENTITIES = (
    "crop_tile_day", "care_feed_payback", "market_impact",
    "town_demand", "shed_overflow", "terminal_inventory",
)


def _private(obs: dict[str, Any]) -> dict[str, Any]:
    """Return only the acting seat's private payload, failing closed."""
    forbidden = {"opponent_private", "future", "next_observation", "replay"}
    if forbidden.intersection(obs):
        raise EngineDriftError("future/opponent-private/replay state is forbidden")
    private = obs.get("private")
    if not isinstance(private, dict) or not isinstance(private.get("shed"), dict):
        raise EngineDriftError("own private shed identity is missing")
    if not isinstance(private.get("seeds"), dict) or not isinstance(private.get("inventories"), list):
        raise EngineDriftError("own private inventory identity is missing")
    return private


def inventory(obs: dict[str, Any]) -> Counter[str]:
    private = _private(obs)
    result: Counter[str] = Counter(private["shed"])
    result.update(private["seeds"])
    for carried in private["inventories"]:
        if not isinstance(carried, dict):
            raise EngineDriftError("own carried inventory identity is malformed")
        result.update(carried)
    return result


def inventory_value(obs: dict[str, Any], snapshot: dict[str, Any]) -> float:
    prices = obs.get("market", {}).get("prices")
    if not isinstance(prices, dict):
        raise EngineDriftError("public market prices are missing")
    value = 0.0
    for item, quantity in inventory(obs).items():
        if item in prices:
            value += quantity * prices[item]
        elif item in snapshot["crops"]:  # seeds are valued at their engine purchase cost.
            value += quantity * snapshot["crops"][item]["seed"]
        elif item in snapshot["animals"]:
            value += quantity * snapshot["animals"][item]["cost"]
    return float(value)


def crop_tile_value(obs: dict[str, Any], seat: int) -> float:
    prices = obs.get("market", {}).get("prices", {})
    farms = obs.get("farms")
    if not isinstance(farms, list) or seat >= len(farms):
        raise EngineDriftError("public own-farm identity is missing")
    value = 0.0
    for row in farms[seat].get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("crop"):
                value += tile.get("yield_units", 0) * prices.get(tile["crop"], 0)
    return float(value)


def animal_payback_value(obs: dict[str, Any], seat: int, snapshot: dict[str, Any]) -> float:
    farms = obs.get("farms", [])
    if seat >= len(farms):
        raise EngineDriftError("public own-farm identity is missing")
    value = 0.0
    for row in farms[seat].get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") in snapshot["animals"]:
                animal = snapshot["animals"][tile["animal"]]
                value += animal["product_base_price"] - animal["feed_cost_to_first_yield"]
                if tile.get("cared_today"):
                    value += animal["care_bonus_value_per_fed_day"]
    return float(value)


def state_values(obs: dict[str, Any], seat: int, snapshot: dict[str, Any]) -> dict[str, float]:
    """Additive own-seat economic state, derived only from allowed observations."""
    inv = inventory(obs)
    prices = obs["market"]["prices"]
    base = {item: data["base"] for item, data in snapshot["market"].items()}
    terminal_base = 0.0
    impact = 0.0
    for item, quantity in inv.items():
        if item in prices:
            terminal_base += quantity * base[item]
            impact += quantity * (prices[item] - base[item])
        elif item in snapshot["crops"]:
            terminal_base += quantity * snapshot["crops"][item]["seed"]
        elif item in snapshot["animals"]:
            terminal_base += quantity * snapshot["animals"][item]["cost"]
    return {
        "crop_tile_day": crop_tile_value(obs, seat),
        "care_feed_payback": animal_payback_value(obs, seat, snapshot),
        "market_impact": float(impact),
        "town_demand": 0.0,  # recorded as public exogenous market flow, never own profit.
        "shed_overflow": 0.0,  # recorded as an inferred loss event below.
        "terminal_inventory": float(terminal_base),
    }


def market_terminal_identity(obs: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, float]:
    """Return the exact engine-price decomposition of own terminal inventory.

    Market value is not an additional reward term: it is base-value inventory
    plus the shared-market price deviation carried by that inventory.  Keeping
    all three values makes double counting mechanically detectable.
    """
    inv = inventory(obs)
    prices = obs.get("market", {}).get("prices")
    if not isinstance(prices, dict):
        raise EngineDriftError("public market prices are missing")
    base = {item: data["base"] for item, data in snapshot["market"].items()}
    terminal_base = 0.0
    market_impact = 0.0
    for item, quantity in inv.items():
        if item in prices:
            terminal_base += quantity * base[item]
            market_impact += quantity * (prices[item] - base[item])
        elif item in snapshot["crops"]:
            terminal_base += quantity * snapshot["crops"][item]["seed"]
        elif item in snapshot["animals"]:
            terminal_base += quantity * snapshot["animals"][item]["cost"]
    market_value = inventory_value(obs, snapshot)
    residual = market_value - terminal_base - market_impact
    return {"terminal_base": float(terminal_base), "market_impact": float(market_impact),
            "market_value": market_value, "identity_residual": float(residual)}


def public_capital_proxy(obs: dict[str, Any], seat: int, snapshot: dict[str, Any]) -> float:
    """Candidate-independent, public-only productive-capital proxy for a seat."""
    farms = obs.get("farms")
    if not isinstance(farms, list) or seat >= len(farms):
        raise EngineDriftError("public farm identity is missing")
    money = farms[seat].get("money")
    if not isinstance(money, (int, float)):
        raise EngineDriftError("public farm money identity is missing")
    return float(money + crop_tile_value(obs, seat) + animal_payback_value(obs, seat, snapshot))


def interaction_transition(obs: dict[str, Any], nxt: dict[str, Any], seat: int,
                           snapshot: dict[str, Any]) -> dict[str, float | bool]:
    """Measure market/terminal co-firing and public opponent-relative exposure."""
    before, after = market_terminal_identity(obs, snapshot), market_terminal_identity(nxt, snapshot)
    terminal_delta = after["terminal_base"] - before["terminal_base"]
    impact_delta = after["market_impact"] - before["market_impact"]
    market_value_delta = after["market_value"] - before["market_value"]
    residual = market_value_delta - terminal_delta - impact_delta
    farms = obs.get("farms", [])
    next_farms = nxt.get("farms", [])
    if len(farms) != 2 or len(next_farms) != 2:
        opponent_delta = 0.0
        opponent_available = False
    else:
        other = 1 - seat
        own_delta = public_capital_proxy(nxt, seat, snapshot) - public_capital_proxy(obs, seat, snapshot)
        other_delta = public_capital_proxy(nxt, other, snapshot) - public_capital_proxy(obs, other, snapshot)
        opponent_delta = own_delta - other_delta
        opponent_available = True
    return {
        "terminal_base_delta": terminal_delta,
        "market_impact_delta": impact_delta,
        "market_value_delta": market_value_delta,
        "identity_residual": residual,
        "market_terminal_fired": terminal_delta != 0.0 and impact_delta != 0.0,
        "opponent_relative_capital_delta": opponent_delta,
        "opponent_exposure_fired": opponent_available and impact_delta != 0.0 and opponent_delta != 0.0,
    }


def planned_values(action: Any, obs: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, float]:
    values = {name: 0.0 for name in IDENTITIES}
    if not isinstance(action, dict):
        return values
    prices = obs.get("market", {}).get("prices", {})
    for order in action.get("market", []) or []:
        if not isinstance(order, list) or not order:
            continue
        name = order[0]; item = order[1] if len(order) > 1 else ""; n = int(order[2]) if len(order) > 2 else 1
        if name == "SELL": values["terminal_inventory"] -= n * prices.get(item, 0)
        elif name == "BUY_SEED" and item in snapshot["crops"]:
            values["terminal_inventory"] += n * snapshot["crops"][item]["seed"]
        elif name == "BUY_ANIMAL" and item in snapshot["animals"]:
            values["care_feed_payback"] += n * snapshot["animals"][item]["first_yield_net"]
    return values


def transition(obs: dict[str, Any], nxt: dict[str, Any], action: Any, seat: int,
               snapshot: dict[str, Any], *, end_of_day: bool) -> dict[str, dict[str, float]]:
    before, after = state_values(obs, seat, snapshot), state_values(nxt, seat, snapshot)
    planned = planned_values(action, obs, snapshot)
    realized = {name: after[name] - before[name] for name in IDENTITIES}
    # Inventory disappearance at the day boundary is attributed explicitly to overflow.
    if end_of_day:
        # Do not confuse sales/feed/planting on the boundary turn with overflow.
        # Only inventory already observably above the engine cap can be assigned.
        shed = _private(obs)["shed"]
        excess = max(0, sum(max(0, int(q)) for q in shed.values()) - snapshot["shed"]["default_capacity"])
        if excess:
            prices = obs["market"]["prices"]
            # A conservative lower bound: excess units at the cheapest visible price.
            realized["shed_overflow"] = -float(excess * min(prices.values()))
    return {name: {"planned": planned[name], "realized": realized[name],
                   "gap": realized[name] - planned[name]} for name in IDENTITIES}

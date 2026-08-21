"""Clean-room Strict-Future meta-reset overlay for an independent whole agent.

This file is appended to the repository champion by the package builder.  It
does not contain or reconstruct the source notebook's route or replay actions.
"""

STRICT_FUTURE_META_RESET = False
STRICT_FUTURE_META_RESET_FIRES = {"sheep_first": 0, "sell_reorder": 0}
_STRICT_FUTURE_BASE_AGENT = agent


def _strict_future_sell_score(obs, order):
    """Rank an existing SELL slot from current public market/town state only."""
    product = str(order[1])
    market = obs.get("market", {})
    price = max(0, int(market.get("prices", {}).get(product, 0)))
    inventory = max(0, int(market.get("inventory", {}).get(product, 0)))
    shops = obs.get("town", {}).get("unlocked_shops", ()) or ()
    demand = sum(product in str(shop) for shop in shops)
    # Scarce, currently demanded goods receive the earliest existing slot.
    return (demand, price, -inventory, product)


def _strict_future_reset(obs, action):
    amended = {
        "farmer": list(action.get("farmer", ["PASS"])),
        "hands": [list(order) for order in action.get("hands", ())],
        "market": [list(order) for order in action.get("market", ())],
    }
    step = max(0, int(obs.get("step", 0)))
    market = amended["market"]

    # A coherent sheep-first opening basin: retain the whole agent's order
    # budget and quantities, but redirect opening cattle acquisition to sheep.
    # This is deliberately bounded to the opening and creates no new order.
    if step < 168:
        cattle = [order for order in market
                  if len(order) >= 2 and order[:2] == ["BUY_ANIMAL", "COW"]]
        if cattle:
            for order in cattle:
                order[1] = "SHEEP"
            STRICT_FUTURE_META_RESET_FIRES["sheep_first"] += 1

    # Preserve every ordinary SELL verb/product/quantity and every non-SELL
    # slot.  Only the order assigned to already-existing SELL slots may move.
    sell_slots = [index for index, order in enumerate(market)
                  if len(order) >= 3 and order[0] == "SELL"]
    sells = [market[index] for index in sell_slots]
    reordered = sorted(sells, key=lambda order: _strict_future_sell_score(obs, order), reverse=True)
    if sells != reordered:
        for index, order in zip(sell_slots, reordered):
            market[index] = order
        STRICT_FUTURE_META_RESET_FIRES["sell_reorder"] += 1
    return amended


def _strict_future_agent(obs):
    action = _STRICT_FUTURE_BASE_AGENT(obs)
    if not STRICT_FUTURE_META_RESET:
        return action
    return _strict_future_reset(obs, action)


# Reinsert the official entrypoint last for the repository's exec validator.
del agent
agent = _strict_future_agent

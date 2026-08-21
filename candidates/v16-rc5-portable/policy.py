"""Clean-room V16-RC5-style 8C/4S and premium-market overlay.

This module is appended to the repository champion by the package builder.  It
contains no copied route, compressed action table, replay identity, or source
notebook code.  It uses only the current observation and the champion action.
"""

V16_RC5_PORTABLE = False
V16_RC5_FIRES = {"herd_target": 0, "premium_timing": 0}
_V16_RC5_BASE_AGENT = agent
_V16_PREMIUM = ("MELON", "MILK", "STRAWBERRY", "WOOL")


def _v16_counts(obs):
    animals = obs.get("private", {}).get("animals", {})
    if not isinstance(animals, dict):
        return {"COW": 0, "SHEEP": 0}
    return {kind: max(0, int(animals.get(kind, 0))) for kind in ("COW", "SHEEP")}


def _v16_target(step):
    """Publicly described herd milestones, expressed without a route trace."""
    if step < 120:
        return {"COW": 1, "SHEEP": 4}
    if step < 161:
        return {"COW": 2, "SHEEP": 4}
    if step < 168:
        return {"COW": 4, "SHEEP": 4}
    if step < 192:
        return {"COW": 6, "SHEEP": 4}
    return {"COW": 8, "SHEEP": 4}


def _v16_rc5_transform(obs, action):
    amended = {
        "farmer": list(action.get("farmer", ["PASS"])),
        "hands": [list(order) for order in action.get("hands", ())],
        "market": [list(order) for order in action.get("market", ())],
    }
    step = max(0, int(obs.get("step", 0)))
    counts, target = _v16_counts(obs), _v16_target(step)

    # Preserve the base agent's purchase slots and quantities.  When it elects
    # to buy livestock, assign each slot to the currently largest target
    # deficit, making the 8C/4S plan inventory-feasible without inventing cash.
    changed = False
    projected = dict(counts)
    for order in amended["market"]:
        if len(order) < 3 or order[0] != "BUY_ANIMAL":
            continue
        amount = max(0, int(order[2]))
        kind = max(("COW", "SHEEP"),
                   key=lambda name: (target[name] - projected[name], name == "SHEEP"))
        if target[kind] > projected[kind] and order[1] != kind:
            order[1] = kind
            changed = True
        projected[str(order[1])] = projected.get(str(order[1]), 0) + amount
    if changed:
        V16_RC5_FIRES["herd_target"] += 1

    # Queue scarce, demanded premium goods first, while preserving every SELL
    # product/quantity and all non-SELL slots.  Own shed stock is a feasibility
    # bound; a sale that exceeds stock is never promoted ahead of another sale.
    shed = obs.get("private", {}).get("shed", {})
    shed = shed if isinstance(shed, dict) else {}
    market = obs.get("market", {})
    prices = market.get("prices", {}) if isinstance(market, dict) else {}
    stock = market.get("inventory", {}) if isinstance(market, dict) else {}
    shops = obs.get("town", {}).get("unlocked_shops", ()) or ()
    slots = [index for index, order in enumerate(amended["market"])
             if len(order) >= 3 and order[0] == "SELL" and order[1] in _V16_PREMIUM]
    sells = [amended["market"][index] for index in slots]

    def score(order):
        item, quantity = str(order[1]), max(0, int(order[2]))
        feasible = quantity <= max(0, int(shed.get(item, 0)))
        demanded = any(item in str(shop) for shop in shops)
        return (feasible, demanded, max(0, int(prices.get(item, 0))),
                -max(0, int(stock.get(item, 0))), item)

    ordered = sorted(sells, key=score, reverse=True)
    if ordered != sells:
        for index, order in zip(slots, ordered):
            amended["market"][index] = order
        V16_RC5_FIRES["premium_timing"] += 1
    return amended


def _v16_rc5_agent(obs):
    action = _V16_RC5_BASE_AGENT(obs)
    if not V16_RC5_PORTABLE:
        return action
    return _v16_rc5_transform(obs, action)


del agent
agent = _v16_rc5_agent

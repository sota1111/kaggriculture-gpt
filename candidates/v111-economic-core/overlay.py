"""Clean-room V111-style 8C/4S economic-core overlay for an MIT whole agent.

The opaque replay schedule from the public notebook is deliberately excluded.
This overlay changes the independently licensed whole-agent foundation as a
coherent package: a four-sheep herd ceiling and inventory-feasible priority for
premium SELL orders.  It never imports or calls the repository champion.
"""

SHEEP_MAX = 4
V111_FIRES = {"premium_order": 0}
_V111_BASE_AGENT = agent
_V111_PREMIUM = {"MELON", "MILK", "STRAWBERRY", "WOOL"}


def _v111_transform(obs, action):
    amended = {
        "farmer": list(action.get("farmer", ["PASS"])),
        "hands": [list(order) for order in action.get("hands", ())],
        "market": [list(order) for order in action.get("market", ())],
    }
    shed = obs.get("private", {}).get("shed", {})
    shed = shed if isinstance(shed, dict) else {}
    market = obs.get("market", {})
    prices = market.get("prices", {}) if isinstance(market, dict) else {}
    inventory = market.get("inventory", {}) if isinstance(market, dict) else {}
    slots = [index for index, order in enumerate(amended["market"])
             if len(order) >= 3 and order[0] == "SELL" and order[1] in _V111_PREMIUM]
    sells = [amended["market"][index] for index in slots]

    def priority(order):
        item, quantity = str(order[1]), max(0, int(order[2]))
        feasible = quantity <= max(0, int(shed.get(item, 0)))
        return (feasible, max(0, int(prices.get(item, 0))),
                -max(0, int(inventory.get(item, 0))), item)

    ordered = sorted(sells, key=priority, reverse=True)
    if ordered != sells:
        for index, order in zip(slots, ordered):
            amended["market"][index] = order
        V111_FIRES["premium_order"] += 1
    return amended


def agent(obs):
    return _v111_transform(obs, _V111_BASE_AGENT(obs))

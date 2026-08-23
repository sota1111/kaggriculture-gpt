"""Clean-room v25 adaptation for an independent Apache-2.0 whole-agent base.

Only the notebook's prose-level interventions are reproduced: a sheep-first
opening basin and public-market ordering of SELL slots already emitted by the
base policy.  The replay-reconstructed 719-action backbone is intentionally
excluded.
"""

V25_STRICT_FUTURE_FIRES = {"sell_reorder": 0}
_V25_BASE_AGENT = agent

# Replace the foundation's livestock preference with a state-independent,
# sheep-first basin. This is a compact strategic parameter, not an action tape.
ANIMAL_SEQ = (["SHEEP", "SHEEP", "COW"] * 20)


def _v25_sell_score(obs, order):
    product = str(order[1])
    public_market = obs.get("market", {}) or {}
    price = max(0, int((public_market.get("prices", {}) or {}).get(product, 0)))
    inventory = max(0, int((public_market.get("inventory", {}) or {}).get(product, 0)))
    shops = (obs.get("town", {}) or {}).get("unlocked_shops", ()) or ()
    demand = sum(product in str(shop) for shop in shops)
    return demand, price, -inventory, product


def _v25_agent(obs):
    action = _V25_BASE_AGENT(obs)
    market = [list(order) for order in action.get("market", ())]
    slots = [i for i, order in enumerate(market)
             if len(order) >= 3 and order[0] == "SELL"]
    sells = [market[i] for i in slots]
    ordered = sorted(sells, key=lambda order: _v25_sell_score(obs, order), reverse=True)
    if sells != ordered:
        for slot, order in zip(slots, ordered):
            market[slot] = order
        V25_STRICT_FUTURE_FIRES["sell_reorder"] += 1
    return {"farmer": action.get("farmer", ["PASS"]),
            "hands": action.get("hands", []), "market": market}


del agent
agent = _v25_agent

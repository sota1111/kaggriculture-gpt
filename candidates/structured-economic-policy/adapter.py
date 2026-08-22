"""Clean-room structured-economic controls for the MIT foundation."""

ECONOMIC_FIRES = {"demand_plan": 0, "sale_first": 0, "terminal_guard": 0,
                  "labor_ceiling": 0}
MILK_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}


def _shop_count(obs, names):
    shops = list(obs.get("town", {}).get("unlocked_shops", ()) or ())
    return sum(shop in names for shop in shops)


def _apply_economic_plan(obs):
    """Size the whole production program from observed demand and horizon."""
    global COW_MAX, SHEEP_MAX, STRAWBERRY_MAX, MAX_HANDS, LAST_ANIMAL_DAY
    day = int(obs.get("day", int(obs.get("step", 0)) // 24))
    yarn = _shop_count(obs, {"YARN_STORE"})
    milk = _shop_count(obs, MILK_SHOPS)
    berry = _shop_count(obs, {"CAKE_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "JAM_SHOP"})
    COW_MAX = min(12, 6 + 2 * milk)
    SHEEP_MAX = min(10, 4 + 2 * yarn)
    STRAWBERRY_MAX = min(36, 16 + 4 * berry)
    LAST_ANIMAL_DAY = 16
    MAX_HANDS = 12 if day < 20 else 13
    if day >= 28:
        COW_MAX = SHEEP_MAX = STRAWBERRY_MAX = 0
        MAX_HANDS = 8
        ECONOMIC_FIRES["terminal_guard"] += 1
    ECONOMIC_FIRES["demand_plan"] += 1
    ECONOMIC_FIRES["labor_ceiling"] += 1


def _market_orders(obs, me, priv, surv, wanted):
    """Preserve field cash, then place liquidations before capital orders."""
    orders = _foundation_market_orders(obs, me, priv, surv, wanted)
    day = int(obs.get("day", int(obs.get("step", 0)) // 24))
    sells = [order for order in orders if order and order[0] == "SELL"]
    buys = [order for order in orders if not order or order[0] != "SELL"]
    if day >= 28:
        buys = [order for order in buys if order and order[0] not in
                {"BUY_ANIMAL", "BUY_SEED", "BUY_LAND", "HIRE_HAND"}]
    result = (sells + buys)[:10]
    if sells and result != orders[:10]:
        ECONOMIC_FIRES["sale_first"] += 1
    return result


def agent(obs):
    normalized = dict(obs)
    normalized.setdefault("day", int(normalized.get("step", 0)) // 24)
    normalized.setdefault("hour", int(normalized.get("step", 0)) % 24)
    _apply_economic_plan(normalized)
    return _foundation_agent(normalized)

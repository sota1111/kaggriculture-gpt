"""Clean-room market-aware whole-policy controls for the MIT farm foundation."""

MARKET_FIRES = {
    "regime_observed": 0,
    "dairy_farm": 0,
    "fiber_farm": 0,
    "produce_farm": 0,
    "terminal_guard": 0,
}
DAIRY_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
PRODUCE_SHOPS = {"CAKE_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "JAM_SHOP"}


def _count_shops(obs, names):
    unlocked = tuple(obs.get("town", {}).get("unlocked_shops", ()) or ())
    return sum(name in names for name in unlocked)


def _select_farm(obs):
    """Select a coherent foundation plan solely from public market demand."""
    global COW_MAX, SHEEP_MAX, STRAWBERRY_MAX, MAX_HANDS, LAST_ANIMAL_DAY
    day = int(obs.get("day", int(obs.get("step", 0)) // 24))
    dairy = _count_shops(obs, DAIRY_SHOPS)
    fiber = _count_shops(obs, {"YARN_STORE"})
    produce = _count_shops(obs, PRODUCE_SHOPS)
    scores = {
        "dairy_farm": dairy * 3,
        "fiber_farm": fiber * 4,
        "produce_farm": produce * 2,
    }
    regime = max(
        ("dairy_farm", "fiber_farm", "produce_farm"),
        key=lambda name: (scores[name], name == "dairy_farm"),
    )
    if regime == "fiber_farm":
        COW_MAX, SHEEP_MAX, STRAWBERRY_MAX, MAX_HANDS = 4, 10, 12, 12
    elif regime == "produce_farm":
        COW_MAX, SHEEP_MAX, STRAWBERRY_MAX, MAX_HANDS = 5, 4, 36, 13
    else:
        COW_MAX, SHEEP_MAX, STRAWBERRY_MAX, MAX_HANDS = 10, 4, 16, 12
    LAST_ANIMAL_DAY = 16
    if day >= 28:
        COW_MAX = SHEEP_MAX = STRAWBERRY_MAX = 0
        MAX_HANDS = 8
        MARKET_FIRES["terminal_guard"] += 1
    MARKET_FIRES["regime_observed"] += 1
    MARKET_FIRES[regime] += 1
    return regime


def agent(obs):
    normalized = dict(obs)
    normalized.setdefault("day", int(normalized.get("step", 0)) // 24)
    normalized.setdefault("hour", int(normalized.get("step", 0)) % 24)
    _select_farm(normalized)
    return _foundation_agent(normalized)  # noqa: F821 - injected pinned foundation

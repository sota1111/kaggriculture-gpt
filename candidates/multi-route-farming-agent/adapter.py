"""Clean-room three-family route selector for the pinned MIT foundation."""

ROUTE_FIRES = {"yarn_led": 0, "milk_supported": 0, "balanced": 0}
SELECTED_ROUTE = None
ROUTES = {
    "yarn_led": (4, 12, 8),
    "milk_supported": (12, 4, 16),
    "balanced": (8, 8, 20),
}
MILK_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}


def select_route(obs):
    """Choose a complete route foundation from public early shop order only."""
    shops = list(obs.get("town", {}).get("unlocked_shops", ()) or ())[:3]
    yarn_position = shops.index("YARN_STORE") if "YARN_STORE" in shops else None
    if yarn_position is not None and yarn_position <= 1:
        return "yarn_led"
    if MILK_SHOPS.intersection(shops[:2]):
        return "milk_supported"
    return "balanced"


def agent(obs):
    global COW_MAX, SHEEP_MAX, STRAWBERRY_MAX, SELECTED_ROUTE
    normalized = dict(obs)
    normalized.setdefault("hour", int(normalized.get("step", 0)) % 24)
    shops = list(normalized.get("town", {}).get("unlocked_shops", ()) or ())
    if SELECTED_ROUTE is None and len(shops) >= 3:
        SELECTED_ROUTE = select_route(normalized)
    route = SELECTED_ROUTE or "balanced"
    ROUTE_FIRES[route] += 1
    COW_MAX, SHEEP_MAX, STRAWBERRY_MAX = ROUTES[route]
    return _foundation_agent(normalized)

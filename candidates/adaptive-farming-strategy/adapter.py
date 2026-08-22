"""Clean-room adaptive route selector for the MIT lonespear foundation.

This file is appended to the pinned foundation at build time, producing one
stdlib-only submission entrypoint.  It uses only the public shop prefix and
never reads episode identity, seed, opponent-private state, or future state.
"""

ROUTE_FIRES = {
    "yarn_first": 0,
    "yarn_second": 0,
    "yarn_third": 0,
    "milk_support": 0,
    "generalist": 0,
}
ROUTES = {
    "yarn_first": (4, 12, 8),
    "yarn_second": (6, 10, 12),
    "yarn_third": (6, 8, 16),
    "milk_support": (12, 2, 20),
    "generalist": (8, 6, 24),
}
MILK_SUPPORT_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}


def select_route(obs):
    """Map the first three unlocked public shops to one coherent season route."""
    shops = list(obs.get("town", {}).get("unlocked_shops", ()) or ())[:3]
    if shops[:1] == ["YARN_STORE"]:
        return "yarn_first"
    if "YARN_STORE" in shops[:2]:
        return "yarn_second"
    if "YARN_STORE" in shops:
        return "yarn_third"
    if MILK_SUPPORT_SHOPS.intersection(shops):
        return "milk_support"
    return "generalist"


def agent(obs):
    """Apply a persistent-demand route while retaining foundation repairs."""
    global COW_MAX, SHEEP_MAX, STRAWBERRY_MAX
    normalized = dict(obs)
    normalized.setdefault("hour", int(normalized.get("step", 0)) % 24)
    route = select_route(normalized)
    ROUTE_FIRES[route] += 1
    COW_MAX, SHEEP_MAX, STRAWBERRY_MAX = ROUTES[route]
    return _foundation_agent(normalized)

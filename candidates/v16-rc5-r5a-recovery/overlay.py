"""Clean-room R5A livestock-alignment recovery for an MIT whole agent.

The public notebook's replay-derived route and executable are intentionally
excluded.  This overlay implements only the described public-state recovery:
an actor carrying a cow whose planned placement tile is blocked moves to an
adjacent empty pasture, places the cow on the next turn, then returns control
to the independently licensed foundation.
"""

R5A_RECOVERY_WINDOW = (160, 210)
R5A_RECOVERY_FIRES = {"align": 0, "place": 0, "resume": 0}
_R5A_BASE_AGENT = agent
_R5A_STATE = {0: {"last_step": -1, "active": {}}, 1: {"last_step": -1, "active": {}}}


def _r5a_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    return getter(key, default) if callable(getter) else getattr(value, key, default)


def _r5a_seat(obs):
    return 1 if int(_r5a_get(obs, "player", 0) or 0) == 1 else 0


def _r5a_farm(obs):
    farms = list(_r5a_get(obs, "farms", []) or [])
    seat = _r5a_seat(obs)
    return farms[seat] if seat < len(farms) else {}


def _r5a_tile(farm, position):
    try:
        x, y = int(position[0]), int(position[1])
        return (_r5a_get(farm, "tiles", []) or [])[y][x]
    except (IndexError, TypeError, ValueError):
        return "LOCKED"


def _r5a_empty_pasture(tile):
    return isinstance(tile, dict) and tile.get("kind") == "PASTURE" and not tile.get("animal")


def _r5a_adjacent_move(farm, position):
    try:
        x, y = int(position[0]), int(position[1])
    except (IndexError, TypeError, ValueError):
        return None
    for operation, dx, dy in (("EAST", 1, 0), ("WEST", -1, 0), ("SOUTH", 0, 1), ("NORTH", 0, -1)):
        if _r5a_empty_pasture(_r5a_tile(farm, (x + dx, y + dy))):
            return [operation]
    return None


def _r5a_cow_inventory(obs, actor_index):
    inventories = list(_r5a_get(_r5a_get(obs, "private", {}) or {}, "inventories", []) or [])
    if actor_index >= len(inventories):
        return 0
    return max(0, int(_r5a_get(inventories[actor_index] or {}, "COW", 0) or 0))


def _r5a_copy(action):
    action = action if isinstance(action, dict) else {}
    return {"farmer": list(action.get("farmer") or ["PASS"]),
            "hands": [list(order or ["PASS"]) for order in (action.get("hands") or [])],
            "market": [list(order) for order in (action.get("market") or [])]}


def _r5a_recover(obs, action):
    step = max(0, int(_r5a_get(obs, "step", 0) or 0))
    seat = _r5a_seat(obs)
    state = _R5A_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {"last_step": step, "active": {}}
        _R5A_STATE[seat] = state
    state["last_step"] = step
    active = state.setdefault("active", {})
    if step % 24 == 0:
        active.clear()

    amended = _r5a_copy(action)
    farm = _r5a_farm(obs)
    positions = [_r5a_get(farm, "farmer"), *list(_r5a_get(farm, "hands", []) or [])]
    orders = [amended["farmer"], *amended["hands"]]

    for actor, transaction in list(active.items()):
        index = 0 if actor == "farmer" else int(actor) + 1
        if index >= len(orders):
            active.pop(actor, None)
            continue
        age = step - int(transaction["start"])
        if age == 1 and _r5a_cow_inventory(obs, index) > 0:
            orders[index] = ["PLACE", "COW", 1]
            R5A_RECOVERY_FIRES["place"] += 1
        elif age >= 2:
            active.pop(actor, None)
            R5A_RECOVERY_FIRES["resume"] += 1

    if R5A_RECOVERY_WINDOW[0] <= step <= R5A_RECOVERY_WINDOW[1]:
        for index, (position, order) in enumerate(zip(positions, orders)):
            actor = "farmer" if index == 0 else index - 1
            if actor in active or order[:2] != ["PLACE", "COW"] or _r5a_cow_inventory(obs, index) <= 0:
                continue
            if _r5a_empty_pasture(_r5a_tile(farm, position)):
                continue
            movement = _r5a_adjacent_move(farm, position)
            if movement:
                active[actor] = {"start": step}
                orders[index] = movement
                R5A_RECOVERY_FIRES["align"] += 1

    amended["farmer"], amended["hands"] = orders[0], orders[1:]
    return amended


def r5a_recovery_telemetry():
    return dict(R5A_RECOVERY_FIRES)


def agent(obs):
    return _r5a_recover(obs, _R5A_BASE_AGENT(obs))

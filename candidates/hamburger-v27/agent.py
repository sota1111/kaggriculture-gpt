"""Clean-room Hamburger V27 whole-agent baseline.

This module implements the public behavioural specification without embedding
or importing the upstream notebook source.  The deterministic anchor remains
available whenever state-aware planning cannot prove a safe intervention.
"""

from collections import Counter

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "EGG", "MILK", "WOOL", "FERTILIZER")
BASE_PRICE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
              "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200,
              "FERTILIZER": 100}
GLUT = {"WHEAT": .2, "CARROT": .7, "TOMATO": .6, "STRAWBERRY": 1.6,
        "MELON": 3.6, "EGG": .2, "MILK": 1.6, "WOOL": 3.2,
        "FERTILIZER": .4}
MOVES = (("NORTH", 0, -1), ("SOUTH", 0, 1),
         ("EAST", 1, 0), ("WEST", -1, 0))
TRACE = Counter()


def _get(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def _pass(hands=0):
    return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(hands)], "market": []}


def _farm(obs):
    farms = _get(obs, "farms", ()) or ()
    player = int(_get(obs, "player", 0) or 0)
    return farms[player] if 0 <= player < len(farms) else None


def _positions(farm):
    return [list(_get(farm, "farmer", (0, 0)) or (0, 0)),
            *[list(p) for p in (_get(farm, "hands", ()) or ())]]


def _move(position, target, tiles):
    x, y = map(int, position)
    choices = []
    for name, dx, dy in MOVES:
        nx, ny = x + dx, y + dy
        if 0 <= ny < len(tiles) and 0 <= nx < len(tiles[ny]) and tiles[ny][nx] != "LOCKED":
            choices.append((abs(nx-target[0]) + abs(ny-target[1]), name))
    return [min(choices)[1]] if choices else ["PASS"]


def _anchor_action(obs, farm):
    """Deterministic, state-derived whole-agent anchor; never external replay data."""
    private = _get(obs, "private", {}) or {}
    seeds = _get(private, "seeds", {}) or {}
    prices = _get(_get(obs, "market", {}) or {}, "prices", {}) or {}
    tiles = _get(farm, "tiles", ()) or ()
    targets = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row or ()):
            if tile == "LOCKED":
                continue
            if isinstance(tile, dict):
                if tile.get("kind") == "WEED": targets.append((0, x, y, ["DIG"]))
                elif tile.get("kind") == "PLANT" and (tile.get("harvestable") or tile.get("ripe")):
                    targets.append((1, x, y, ["HARVEST"]))
                elif tile.get("kind") == "PLANT" and not tile.get("watered_today", False):
                    targets.append((2, x, y, ["WATER"]))
                elif tile.get("animal") and not tile.get("fed_today", False):
                    targets.append((2, x, y, ["FEED"]))
                elif tile.get("animal") and not tile.get("cared_today", False):
                    targets.append((3, x, y, ["CARE"]))
                elif tile.get("harvestable") or tile.get("product_ready"):
                    targets.append((1, x, y, ["HARVEST"]))
            elif tile is None:
                crops = [c for c in BASE_PRICE if c in seeds and int(seeds.get(c, 0) or 0) > 0]
                if crops:
                    crop = max(crops, key=lambda c: (int(prices.get(c, BASE_PRICE[c]) or 0), c))
                    targets.append((4, x, y, ["PLANT", crop]))
    claimed, actions = set(), []
    for position in _positions(farm):
        choices = [(priority, abs(int(position[0])-x)+abs(int(position[1])-y), x, y, action)
                   for priority, x, y, action in targets if (x, y) not in claimed]
        if not choices:
            actions.append(["PASS"]); continue
        _, _, x, y, action = min(choices)
        claimed.add((x, y))
        actions.append(action if tuple(map(int, position)) == (x, y)
                       else _move(position, (x, y), tiles))
    TRACE["anchor_calls"] += 1
    return {"farmer": actions[0], "hands": actions[1:], "market": []}


def _opponent_exposure(obs):
    farms = _get(obs, "farms", ()) or ()
    player = int(_get(obs, "player", 0) or 0)
    if len(farms) != 2:
        return Counter()
    counts = Counter()
    for row in (_get(farms[1-player], "tiles", ()) or ()):
        for tile in row or ():
            if isinstance(tile, dict):
                key = tile.get("animal") or tile.get("crop")
                if key: counts[key] += 1
    return counts


def _collision_sells(obs, shed):
    prices = _get(_get(obs, "market", {}) or {}, "prices", {}) or {}
    exposure = _opponent_exposure(obs)
    product_exposure = {"EGG": exposure["GOOSE"], "MILK": exposure["COW"],
                        "WOOL": exposure["SHEEP"], "FERTILIZER": sum(exposure[a] for a in ("GOOSE", "COW", "SHEEP"))}
    orders = []
    for item in PRODUCTS:
        quantity = max(0, int(_get(shed, item, 0) or 0))
        if quantity:
            rival = product_exposure.get(item, exposure[item])
            price = float(prices.get(item, BASE_PRICE[item]) or 0)
            score = price * min(quantity, 12) + .075 * price * min(quantity, 8) * rival * GLUT[item]
            orders.append((score, price * quantity, item, quantity))
    orders.sort(reverse=True)
    TRACE["collision_sell_calls"] += bool(orders)
    return [["SELL", item, quantity] for _, _, item, quantity in orders[:10]]


def _access_tiles(tiles):
    half = len(tiles) // 2
    return [(x, y) for x, y in ((half-1, half-1), (half, half-1), (half-1, half), (half, half))
            if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) and tiles[y][x] != "LOCKED"]


def _terminal_relay(action, obs, farm, step):
    if not 716 <= step <= 718:
        return action
    private = _get(obs, "private", {}) or {}
    shed = dict(_get(private, "shed", {}) or {})
    inventories = _get(private, "inventories", ()) or ()
    tiles, positions = _get(farm, "tiles", ()) or (), _positions(farm)
    access, room, projected = _access_tiles(tiles), max(0, 100-sum(max(0, int(v or 0)) for v in shed.values())), Counter()
    actor_actions = [list(action["farmer"]), *[list(a) for a in action["hands"]]]
    for index, position in enumerate(positions):
        inv = inventories[index] if index < len(inventories) else {}
        products = {k: max(0, int(v or 0)) for k, v in (inv or {}).items() if k in PRODUCTS and int(v or 0) > 0}
        if not products or not access: continue
        if tuple(map(int, position)) in set(access) and room:
            total = sum(products.values())
            if total == sum(max(0, int(v or 0)) for v in (inv or {}).values()) and total <= room:
                actor_actions[index] = ["DROP"]; take = products
            else:
                item = max(products, key=lambda k: (BASE_PRICE[k] * products[k] * (1+GLUT[k]), k))
                take = {item: min(products[item], room)}
                actor_actions[index] = ["PLACE", item, take[item]]
            projected.update(take); room -= sum(take.values())
        elif step < 718 and actor_actions[index][0] in ("PASS", "PLACE", "DROP"):
            target = min(access, key=lambda p: abs(int(position[0])-p[0])+abs(int(position[1])-p[1]))
            actor_actions[index] = _move(position, target, tiles)
    action["farmer"], action["hands"] = actor_actions[0], actor_actions[1:]
    combined = Counter({k: max(0, int(v or 0)) for k, v in shed.items() if k in PRODUCTS})
    combined.update(projected)
    action["market"] = _collision_sells(obs, combined)
    TRACE["terminal_relay_calls"] += 1
    return action


def trace_snapshot():
    return dict(TRACE)


def agent(obs, config=None):
    try:
        farm = _farm(obs)
        if farm is None or not (_get(farm, "tiles", ()) or ()):
            raise ValueError("unsupported observation")
        step = max(0, min(718, int(_get(obs, "step", 0) or 0)))
        action = _anchor_action(obs, farm)
        private = _get(obs, "private", {}) or {}
        action["market"] = _collision_sells(obs, _get(private, "shed", {}) or {})
        return _terminal_relay(action, obs, farm, step)
    except (TypeError, ValueError, IndexError, KeyError):
        TRACE["fallback_calls"] += 1
        return _pass()

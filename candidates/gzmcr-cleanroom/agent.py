"""Independent clean-room role-planned Kaggriculture whole agent."""

from collections import Counter

MOVES = (("NORTH", 0, -1), ("SOUTH", 0, 1), ("EAST", 1, 0), ("WEST", -1, 0))
TRACE = {"calls": 0, "roles": Counter(), "work": Counter(), "invalid": 0}


def _pass(hands=0):
    return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(hands)], "market": []}


def _move(start, target):
    x, y = map(int, start)
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _targets(obs, farm, private):
    seeds = private.get("seeds", {}) or {}
    targets = {"rescue": [], "harvest": [], "care": [], "plant": []}
    for y, row in enumerate(farm.get("tiles", ())):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if tile is None and any(int(v or 0) > 0 for v in seeds.values()):
                targets["plant"].append(((x, y), None))
            elif isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "WEED":
                    targets["rescue"].append(((x, y), ["DIG"]))
                elif kind == "PLANT":
                    if tile.get("harvestable") or tile.get("ripe"):
                        targets["harvest"].append(((x, y), ["HARVEST"]))
                    elif not tile.get("watered_today", False):
                        targets["rescue"].append(((x, y), ["WATER"]))
                elif "animal" in tile:
                    if not tile.get("fed_today", False):
                        targets["rescue"].append(((x, y), ["FEED"]))
                    elif tile.get("harvestable") or tile.get("product_ready"):
                        targets["harvest"].append(((x, y), ["HARVEST"]))
                    elif not tile.get("cared_today", False):
                        targets["care"].append(((x, y), ["CARE"]))
    return targets


def _crop(private, prices):
    seeds = private.get("seeds", {}) or {}
    base = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}
    options = [name for name, count in seeds.items() if name in base and int(count or 0) > 0]
    return max(options, key=lambda name: (int(prices.get(name, base[name])), name)) if options else None


def _work(worker, role, targets, crop, claimed):
    ordered = {
        "steward": ("rescue", "care", "harvest", "plant"),
        "producer": ("harvest", "plant", "rescue", "care"),
        "support": ("care", "rescue", "harvest", "plant"),
    }[role]
    choices = []
    for priority, kind in enumerate(ordered):
        for index, (target, action) in enumerate(targets[kind]):
            identity = (kind, index)
            if identity not in claimed:
                distance = abs(int(worker[0]) - target[0]) + abs(int(worker[1]) - target[1])
                choices.append((priority, distance, target, action, identity, kind))
    if not choices:
        return ["PASS"]
    _, _, target, action, identity, kind = min(choices)
    claimed.add(identity)
    TRACE["work"][kind] += 1
    if tuple(map(int, worker)) == target:
        return ["PLANT", crop] if kind == "plant" and crop else action
    return _move(worker, target)


def _market(obs, farm, private, workload):
    day = max(0, int(obs.get("day", 0)))
    total_days = max(1, int(obs.get("total_days", 30)))
    money = max(0, int(farm.get("money", 0)))
    prices = obs.get("market", {}).get("prices", {}) or {}
    crop = _crop(private, prices) or "WHEAT"
    seeds = private.get("seeds", {}) or {}
    orders = []
    if day < total_days - 5 and int(seeds.get(crop, 0) or 0) < 4 and money > 500:
        orders.append(["BUY_SEED", crop, 4 - int(seeds.get(crop, 0) or 0)])
    if workload > 5 and len(farm.get("hands", ()) or ()) < 3 and money > 800:
        orders.append(["HIRE"])
    for product, quantity in sorted((private.get("shed", {}) or {}).items()):
        quantity = max(0, int(quantity or 0))
        if quantity and (quantity >= 8 or day >= total_days - 2):
            orders.append(["SELL", product, quantity])
    return orders[:10]


def trace_snapshot():
    return {"calls": TRACE["calls"], "roles": dict(TRACE["roles"]),
            "work": dict(TRACE["work"]), "invalid": TRACE["invalid"]}


def agent(obs, config=None):
    try:
        player = int(obs.get("player", 0))
        farms, private = obs.get("farms", ()), obs.get("private")
        if not isinstance(private, dict) or not isinstance(farms, (list, tuple)) or player >= len(farms):
            raise ValueError("unsupported observation")
        farm = farms[player]
        workers = [farm.get("farmer", (0, 0)), *(farm.get("hands", ()) or ())]
        if not farm.get("tiles") or not workers:
            raise ValueError("missing board")
        targets = _targets(obs, farm, private)
        crop = _crop(private, obs.get("market", {}).get("prices", {}) or {})
        claimed, actions = set(), []
        for index, worker in enumerate(workers):
            role = ("steward", "producer", "support")[index % 3]
            TRACE["roles"][role] += 1
            actions.append(_work(worker, role, targets, crop, claimed))
        TRACE["calls"] += 1
        workload = sum(map(len, targets.values()))
        return {"farmer": actions[0], "hands": actions[1:],
                "market": _market(obs, farm, private, workload)}
    except (KeyError, TypeError, ValueError, IndexError):
        TRACE["invalid"] += 1
        return _pass()

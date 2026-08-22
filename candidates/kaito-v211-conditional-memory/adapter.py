"""Clean-room public-state conditional memory for SOT-2985."""
import copy as _cm_copy

MEMORY_INTERVAL = 24
MEMORY_MAX_DISTANCE = 48.0
_CM_SELLABLE = ("MILK", "WOOL", "EGG", "FERTILIZER", "WHEAT", "CORN", "TOMATO", "STRAWBERRY")
_CM_MEMORY = []
_CM_TELEMETRY = {"games": 0, "hit": 0, "miss": 0, "fallback": 0, "reordered": 0}


def _cm_get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _cm_seat(obs):
    return int(_cm_get(obs, "player", _cm_get(obs, "player_id", 0)) or 0)


def _cm_opponent(obs):
    farms = list(_cm_get(obs, "farms", []) or [])
    seat = _cm_seat(obs)
    return farms[1 - seat] if len(farms) == 2 and seat in (0, 1) else None


def _cm_signature(farm):
    if not farm:
        return None
    hands = list(_cm_get(farm, "hands", []) or [])
    unlocked = sorted(str(x) for x in (_cm_get(farm, "unlocked_quadrants", []) or []))
    counts = {name: 0 for name in _CM_SELLABLE}
    positions = []
    for actor in [_cm_get(farm, "farmer", [-1, -1]), *hands]:
        pos = _cm_get(actor, "position", actor)
        try:
            positions.extend((int(pos[0]), int(pos[1])))
        except (IndexError, TypeError, ValueError):
            positions.extend((-1, -1))
    for row in (_cm_get(farm, "tiles", []) or []):
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            crop = str(tile.get("crop", "")).upper()
            animal = str(tile.get("animal", "")).upper()
            if crop in counts:
                counts[crop] += 1 + max(0, int(tile.get("yield_units", 0) or 0))
            product = {"COW": "MILK", "SHEEP": "WOOL", "CHICKEN": "EGG"}.get(animal)
            if product:
                counts[product] += 1 + max(0, int(tile.get("yield_units", 0) or 0))
            if tile.get("fertilizer_available", False):
                counts["FERTILIZER"] += 1
    return {"workers": len(hands), "unlocks": unlocked, "positions": positions[:6],
            "exposure": [counts[name] for name in _CM_SELLABLE]}


def _cm_distance(left, right):
    if left is None or right is None:
        return float("inf")
    distance = 12.0 * abs(left["workers"] - right["workers"])
    distance += 7.0 * len(set(left["unlocks"]) ^ set(right["unlocks"]))
    distance += 0.5 * sum(abs(a - b) for a, b in zip(left["positions"], right["positions"]))
    distance += 2.0 * sum(abs(a - b) for a, b in zip(left["exposure"], right["exposure"]))
    return distance


def _cm_apply(obs, action, step):
    global _CM_MEMORY
    if step == 0:
        _CM_MEMORY = []
        _CM_TELEMETRY["games"] += 1
    base = _cm_copy.deepcopy(action)
    signature = _cm_signature(_cm_opponent(obs))
    if signature is None:
        _CM_TELEMETRY["fallback"] += 1
        return base
    market = list(base.get("market") or []) if isinstance(base, dict) else []
    sells = [order for order in market if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL"]
    earlier = [row for row in _CM_MEMORY if row["step"] < step]
    if not earlier:
        _CM_TELEMETRY["miss"] += 1
    else:
        distance, remembered = min((_cm_distance(signature, row["signature"]), row) for row in earlier)
        if distance > MEMORY_MAX_DISTANCE:
            _CM_TELEMETRY["fallback"] += 1
        else:
            _CM_TELEMETRY["hit"] += 1
            preferred = {name for name, amount in zip(_CM_SELLABLE, remembered["signature"]["exposure"]) if amount > 0}
            reordered = sorted(enumerate(market), key=lambda pair: (0 if len(pair[1]) >= 2 and pair[1][0] == "SELL" and pair[1][1] in preferred else 1, pair[0]))
            updated = [order for _index, order in reordered]
            if updated != market:
                _CM_TELEMETRY["reordered"] += 1
                base["market"] = updated
    if step % MEMORY_INTERVAL == 0:
        _CM_MEMORY.append({"step": step, "signature": signature})
    # The intervention is order-only: it cannot create a SELL or change quantities.
    assert sorted(map(tuple, sells)) == sorted(map(tuple, [o for o in (base.get("market") or []) if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"]))
    return base


def conditional_memory_telemetry():
    return dict(_CM_TELEMETRY)


def agent(obs):
    try:
        base = _foundation_agent(obs)
        step = max(0, int(_cm_get(obs, "step", 0) or 0))
        return _cm_apply(obs, base, step)
    except Exception:
        _CM_TELEMETRY["fallback"] += 1
        try:
            return _foundation_agent(obs)
        except Exception:
            return {"farmer": ["PASS"], "hands": [], "market": []}

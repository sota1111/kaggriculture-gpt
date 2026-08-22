"""Clean-room reactive optimal-task Kaggriculture agent (stdlib only).

This independent hedge turns each live board observation into a fresh set of
jobs, prices jobs by immediate economic value, subtracts travel cost, and then
greedily assigns each job to at most one worker.  It contains no replay,
weights, or copied source from the motivating unlicensed notebook.
"""

from collections import Counter, deque

MOVES = (("NORTH", 0, -1), ("SOUTH", 0, 1), ("EAST", 1, 0), ("WEST", -1, 0))
PASS_ACTION = {"farmer": ["PASS"], "hands": [], "market": []}
TRACE = {"calls": 0, "assigned": Counter(), "unassigned": Counter(), "invalid_observations": 0}


def _pass(hand_count=0):
    return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(hand_count)], "market": []}


def _distance_map(start, tiles):
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    start = tuple(int(value) for value in start)
    distances = {start: 0}
    first = {start: "PASS"}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for verb, dx, dy in MOVES:
            nxt = (x + dx, y + dy)
            nx, ny = nxt
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if nxt in distances or tiles[ny][nx] == "LOCKED":
                continue
            distances[nxt] = distances[(x, y)] + 1
            first[nxt] = verb if (x, y) == start else first[(x, y)]
            queue.append(nxt)
    return distances, first


def _crop_value(crop, prices):
    fallback = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}
    yields = {"WHEAT": 4, "CARROT": 3, "TOMATO": 4, "STRAWBERRY": 4, "MELON": 6}
    return max(20, int(prices.get(crop, fallback.get(crop, 25))) * yields.get(crop, 3))


def _jobs(obs, farm, private):
    day = max(0, int(obs.get("day", 0)))
    prices = obs.get("market", {}).get("prices", {}) or {}
    seeds = private.get("seeds", {}) or {}
    jobs = []
    for y, row in enumerate(farm.get("tiles", ())):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if tile is None:
                available = [crop for crop, count in seeds.items() if int(count or 0) > 0]
                if available:
                    crop = max(available, key=lambda name: (_crop_value(name, prices), name))
                    jobs.append({"kind": "plant", "target": (x, y), "action": ["PLANT", crop],
                                 "value": _crop_value(crop, prices) * 0.55})
                continue
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "WEED":
                jobs.append({"kind": "dig", "target": (x, y), "action": ["DIG"], "value": 150})
            elif kind == "PLANT":
                crop = str(tile.get("crop", "WHEAT"))
                value = _crop_value(crop, prices)
                age = day - int(tile.get("planted_day", day))
                if tile.get("harvestable") or tile.get("ripe") or age >= int(tile.get("maturity_days", 99)):
                    jobs.append({"kind": "harvest", "target": (x, y), "action": ["HARVEST"], "value": value})
                elif not tile.get("watered_today", False):
                    jobs.append({"kind": "water", "target": (x, y), "action": ["WATER"], "value": value * 0.35})
            elif "animal" in tile:
                product = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}.get(tile.get("animal"), "EGG")
                value = max(50, int(prices.get(product, 50)))
                if not tile.get("cared_today", False):
                    jobs.append({"kind": "care", "target": (x, y), "action": ["CARE"], "value": value * 1.5})
                if tile.get("harvestable") or tile.get("product_ready"):
                    jobs.append({"kind": "harvest", "target": (x, y), "action": ["HARVEST"], "value": value * 2})
            elif kind in {"COOP", "PASTURE"}:
                animal = "GOOSE" if kind == "COOP" else "COW"
                jobs.append({"kind": "place", "target": (x, y), "action": ["PLACE", animal], "value": 500})
    return jobs


def _assign(workers, tiles, jobs):
    maps = [_distance_map(worker, tiles) for worker in workers]
    pairs = []
    for worker_index, (distances, _first) in enumerate(maps):
        for job_index, job in enumerate(jobs):
            distance = distances.get(job["target"])
            if distance is not None:
                pairs.append((job["value"] - 24 * distance, -distance, -job_index,
                              worker_index, job_index))
    pairs.sort(reverse=True)
    assigned_workers, assigned_jobs, chosen = set(), set(), {}
    for score, _neg_distance, _neg_job, worker_index, job_index in pairs:
        if score <= 0 or worker_index in assigned_workers or job_index in assigned_jobs:
            continue
        assigned_workers.add(worker_index)
        assigned_jobs.add(job_index)
        chosen[worker_index] = jobs[job_index]
    actions = []
    for worker_index, worker in enumerate(workers):
        job = chosen.get(worker_index)
        if job is None:
            actions.append(["PASS"])
            continue
        TRACE["assigned"][job["kind"]] += 1
        if tuple(worker) == job["target"]:
            actions.append(job["action"])
        else:
            actions.append([maps[worker_index][1][job["target"]]])
    for index, job in enumerate(jobs):
        if index not in assigned_jobs:
            TRACE["unassigned"][job["kind"]] += 1
    return actions


def _market(obs, farm, private, job_count):
    market = []
    prices = obs.get("market", {}).get("prices", {}) or {}
    seeds = private.get("seeds", {}) or {}
    shed = private.get("shed", {}) or {}
    money = max(0, int(farm.get("money", 0)))
    total_days = max(1, int(obs.get("total_days", 30)))
    day = max(0, int(obs.get("day", 0)))
    crop = max(("STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT"),
               key=lambda name: (_crop_value(name, prices), name))
    desired = min(8, max(2, job_count // 3))
    have = max(0, int(seeds.get(crop, 0)))
    price = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}[crop]
    buy = min(max(0, desired - have), max(0, (money - 250) // price))
    if buy and day < total_days - 4:
        market.append(["BUY_SEED", crop, buy])
    if len(farm.get("hands", ())) < min(8, max(1, job_count // 6)) and money > 750:
        market.append(["HIRE"])
    for product in sorted(shed):
        quantity = max(0, int(shed.get(product, 0)))
        if quantity and (day >= total_days - 2 or quantity >= 8):
            market.append(["SELL", product, quantity])
    return market[:10]


def trace_snapshot():
    return {"calls": TRACE["calls"], "assigned": dict(TRACE["assigned"]),
            "unassigned": dict(TRACE["unassigned"]),
            "invalid_observations": TRACE["invalid_observations"]}


def agent(obs, config=None):
    """Return a bounded action from the current observation only."""
    try:
        player = int(obs.get("player", 0))
        farms = obs.get("farms", ())
        if player < 0 or player >= len(farms) or not isinstance(obs.get("private"), dict):
            raise ValueError("unsupported observation")
        farm = farms[player]
        hands = list(farm.get("hands", ()) or ())
        workers = [farm.get("farmer", (0, 0)), *hands]
        tiles = farm.get("tiles", ())
        if not tiles or not workers:
            raise ValueError("missing board")
        jobs = _jobs(obs, farm, obs["private"])
        actions = _assign(workers, tiles, jobs)
        TRACE["calls"] += 1
        return {"farmer": actions[0], "hands": actions[1:],
                "market": _market(obs, farm, obs["private"], len(jobs))}
    except (KeyError, TypeError, ValueError, IndexError):
        TRACE["invalid_observations"] += 1
        return _pass()

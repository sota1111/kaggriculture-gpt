"""Independent clean-room diversified scheduler candidate.

Only the public concepts "one unique job per unit" and a bounded seven-hand
production loop informed this implementation.  No source-notebook code or
route trace is reproduced here.
"""

from functools import lru_cache


DIVERSIFIED_SCHEDULER = False
MAX_HANDS = 7
MOVE = {"NORTH": (0, -1), "SOUTH": (0, 1), "WEST": (-1, 0), "EAST": (1, 0)}
PRODUCTIVE = {"HARVEST", "WATER", "FERTILIZE", "DIG", "PLANT"}
TELEMETRY = {"turns": 0, "unique_jobs": 0, "collisions": 0,
             "productive_actions": 0, "travel_actions": 0}


def _step(position, target):
    x, y = position
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


def _destination(position, action):
    dx, dy = MOVE.get(action[0], (0, 0))
    return position[0] + dx, position[1] + dy


def _task(tile, day, have_seed):
    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        if int(tile.get("yield_units", 0)) > 0:
            return 0, ["HARVEST"]
        if not tile.get("watered_today", False):
            return 1, ["WATER"]
    if tile is None and have_seed:
        return 2, ["PLANT", "WHEAT"]
    return None


def _jobs(farm, day, seed_count):
    jobs = []
    for y, row in enumerate(farm.get("tiles", ())):
        for x, tile in enumerate(row):
            task = _task(tile, day, seed_count > 0)
            if task is not None:
                priority, action = task
                jobs.append((priority, y, x, action))
    return jobs


def _assign_unique(workers, jobs):
    """Globally assign at most one distinct job and destination per unit."""
    jobs = tuple(jobs[:max(len(workers) + 3, len(workers))])

    @lru_cache(maxsize=None)
    def search(index, used, destinations):
        if index == len(workers):
            return (0, 0, 0), ()
        position = tuple(workers[index])
        # All not-yet-processed units reserve their current cell.  Releasing
        # only this unit's cell prevents an earlier unit from moving into a
        # later stationary unit while still allowing standing work.
        occupied = set(destinations)
        occupied.discard(position)
        best = None
        for job_index, (priority, y, x, action) in enumerate(jobs):
            if used & (1 << job_index):
                continue
            distance = abs(position[0] - x) + abs(position[1] - y)
            order = action if distance == 0 else _step(position, (x, y))
            destination = _destination(position, order)
            if destination in occupied:
                continue
            tail_cost, tail = search(index + 1, used | (1 << job_index),
                                     tuple(sorted(occupied | {destination})))
            proposal = ((tail_cost[0] + priority, tail_cost[1] + distance,
                         tail_cost[2] - int(distance == 0)),
                        (job_index,) + tail)
            if best is None or proposal < best:
                best = proposal
        idle_destinations = tuple(sorted(occupied | {position}))
        tail_cost, tail = search(index + 1, used, idle_destinations)
        idle = ((tail_cost[0] + 9, tail_cost[1], tail_cost[2]), (-1,) + tail)
        return idle if best is None or idle < best else best

    choices = search(0, 0, tuple(sorted(tuple(position) for position in workers)))[1]
    orders, targets = [], []
    for position, choice in zip(workers, choices):
        if choice < 0:
            orders.append(["PASS"])
            targets.append(None)
            continue
        _, y, x, action = jobs[choice]
        orders.append(action if list(position) == [x, y] else _step(position, (x, y)))
        targets.append((x, y))
    return orders, targets


def _market(obs, farm, private):
    orders = []
    money = max(0, int(farm.get("money", 0)))
    hands = len(farm.get("hands", ()))
    hires_today = max(0, int(farm.get("hires_today", hands)))
    hire_cost = 100 * (2 ** min(hires_today, 12))
    if hands < MAX_HANDS and money >= hire_cost + 250:
        orders.append(["HIRE"])
    seeds = max(0, int(private.get("seeds", {}).get("WHEAT", 0)))
    if seeds < max(1, 1 + hands) and money >= 20:
        orders.append(["BUY_SEED", "WHEAT", max(1, 1 + hands - seeds)])
    wheat = max(0, int(private.get("shed", {}).get("WHEAT", 0)))
    if wheat and int(obs.get("day", 0)) >= int(obs.get("total_days", 30)) - 1:
        orders.append(["SELL", "WHEAT", wheat])
    return orders[:10]


def diversified_scheduler_agent(obs):
    if not DIVERSIFIED_SCHEDULER:
        return {"farmer": ["PASS"], "hands": [], "market": []}
    seat = int(obs.get("player", 0))
    farms = obs.get("farms", ())
    if seat >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    farm = farms[seat]
    private = obs.get("private", {}) or {}
    workers = [farm.get("farmer", [0, 0]), *farm.get("hands", ())]
    jobs = _jobs(farm, int(obs.get("day", 0)),
                 int(private.get("seeds", {}).get("WHEAT", 0)))
    actions, targets = _assign_unique(workers, jobs)
    destinations = [_destination(tuple(position), action)
                    for position, action in zip(workers, actions)]
    TELEMETRY["turns"] += 1
    TELEMETRY["unique_jobs"] += len({target for target in targets if target is not None})
    TELEMETRY["collisions"] += len(destinations) - len(set(destinations))
    TELEMETRY["productive_actions"] += sum(action[0] in PRODUCTIVE for action in actions)
    TELEMETRY["travel_actions"] += sum(action[0] in MOVE for action in actions)
    return {"farmer": actions[0], "hands": actions[1:],
            "market": _market(obs, farm, private)}


agent = diversified_scheduler_agent

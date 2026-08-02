"""Deterministic multi-worker Kaggriculture agent."""

from functools import lru_cache

HIRE_TARGET = 4
SEED_RESERVE_PER_WORKER = 2
MIN_CASH_RESERVE = 100
MAX_MARKET_ORDERS = 10
CROP_STRATEGY = "BEST_RETURN"
SELL_STRATEGY = "PRICE_AWARE"

DEFAULT_CROPS = {
    "WHEAT": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3, "fallback_price": 15},
}


def _hire_cost(hires_today):
    a, b = 1, 1
    for _ in range(max(0, int(hires_today))):
        a, b = b, a + b
    return a


def _move(position, target):
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


def _next_position(position, action):
    x, y = position
    offsets = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
    dx, dy = offsets.get(action[0], (0, 0))
    return x + dx, y + dy


def _task_priority(tile, day, crop_specs=None):
    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop = tile.get("crop", "WHEAT")
        maturity = int((crop_specs or {}).get(crop, {}).get("maturity_days", 2))
        if int(tile.get("yield_units", 0)) > 0 or day - int(tile.get("planted_day", day)) >= maturity:
            return 0
        if not tile.get("watered_today", False):
            return 1
        return None
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return 2
    if tile is None:
        return 3
    return None


def _action_at(tile, day, available_seeds, crop, crop_specs):
    priority = _task_priority(tile, day, crop_specs)
    if priority == 0:
        return ["HARVEST"], available_seeds
    if priority == 1:
        return ["WATER"], available_seeds
    if priority == 2:
        return ["DIG"], available_seeds
    if priority == 3 and available_seeds > 0:
        return ["PLANT", crop], available_seeds - 1
    return ["PASS"], available_seeds


def _plan_workers(me, day, seeds, crop, crop_specs, hour=0, turns_per_day=12):
    tiles = me["tiles"]
    workers = [me["farmer"]] + list(me.get("hands", []))
    candidates = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            priority = _task_priority(tile, day, crop_specs)
            if priority is not None:
                if priority == 0:
                    distance_to_deadline = 1
                elif priority == 1:
                    distance_to_deadline = max(0, turns_per_day - hour - 1)
                else:
                    distance_to_deadline = turns_per_day + 1
                candidates.append((priority, distance_to_deadline, y, x))

    # A bounded global search is enough for the maximum five workers we hire. Keeping
    # the most urgent nearby tasks avoids factorial growth on a fully open field.
    candidates.sort(key=lambda task: (task[0], task[1], task[2], task[3]))
    candidates = candidates[:max(len(workers), len(workers) + 2)]

    @lru_cache(maxsize=None)
    def assign(worker_index, used_mask, occupied_next):
        if worker_index == len(workers):
            return (0, 0, 0), ()
        px, py = workers[worker_index]
        best = None
        occupied = set(occupied_next)
        for task_index, (priority, deadline, ty, tx) in enumerate(candidates):
            if used_mask & (1 << task_index):
                continue
            distance = abs(tx - px) + abs(ty - py)
            action = _move((px, py), (tx, ty)) if distance else ["PASS"]
            next_position = _next_position((px, py), action)
            conflict = int(next_position in occupied and next_position != (px, py))
            overdue = int(distance > deadline)
            future_cost, future_choices = assign(
                worker_index + 1,
                used_mask | (1 << task_index),
                tuple(sorted(occupied | {next_position})),
            )
            # Deadline misses and movement conflicts dominate travel. Priority weights
            # ensure low-value planting cannot delay harvest/water work.
            cost = (
                future_cost[0] + overdue,
                future_cost[1] + conflict,
                future_cost[2] + priority * 100 + distance * (4 - min(priority, 3)),
            )
            proposal = cost, (task_index,) + future_choices
            if best is None or proposal < best:
                best = proposal
        if best is None:
            future_cost, future_choices = assign(worker_index + 1, used_mask, occupied_next)
            return future_cost, (-1,) + future_choices
        return best

    choices = assign(0, 0, ())[1] if candidates else (-1,) * len(workers)
    actions = []
    for position, choice in zip(workers, choices):
        if choice < 0:
            actions.append(["PASS"])
            continue
        px, py = position
        _, _, ty, tx = candidates[choice]
        if [px, py] == [tx, ty]:
            action, seeds = _action_at(tiles[ty][tx], day, seeds, crop, crop_specs)
        else:
            action = _move(position, (tx, ty))
        actions.append(action)
    return actions


def _crop_specs(obs):
    supplied = obs.get("crops", {})
    specs = {}
    for crop, default in DEFAULT_CROPS.items():
        value = supplied.get(crop, {}) if isinstance(supplied, dict) else {}
        specs[crop] = {**default, **value}
    if isinstance(supplied, dict):
        for crop, value in supplied.items():
            if isinstance(crop, str) and isinstance(value, dict):
                specs[crop] = {**DEFAULT_CROPS["WHEAT"], **value}
    return specs


def _choose_crop(obs, seeds):
    specs = _crop_specs(obs)
    prices = obs.get("market", {}).get("prices", {})
    known = [crop for crop in specs if int(seeds.get(crop, 0)) > 0 or crop in prices]
    if not known or CROP_STRATEGY == "WHEAT_ONLY":
        return "WHEAT", specs

    def daily_return(crop):
        spec = specs[crop]
        sale = int(prices.get(crop, spec["fallback_price"]))
        margin = sale * int(spec["expected_yield"]) - int(spec["seed_price"])
        return margin / max(1, int(spec["maturity_days"])), margin, crop

    return max(known, key=daily_return), specs


def agent(obs):
    me = obs["farms"][int(obs["player"])]
    private = obs["private"]
    day = int(obs.get("day", 0))
    hands = me.get("hands", [])
    worker_count = 1 + len(hands)

    market = []
    money = int(me["money"])
    seed_inventory = private.get("seeds", {})
    crop, crop_specs = _choose_crop(obs, seed_inventory)
    prices = obs.get("market", {}).get("prices", {})
    stored_inventory = private.get("shed", {})
    for stored_crop in sorted(crop_specs):
        stored = int(stored_inventory.get(stored_crop, 0))
        price = int(prices.get(stored_crop, crop_specs[stored_crop]["fallback_price"]))
        target = int(crop_specs[stored_crop].get("sell_above", crop_specs[stored_crop]["fallback_price"]))
        if stored > 0 and (SELL_STRATEGY == "IMMEDIATE" or price >= target or day >= 11):
            market.append(["SELL", stored_crop, stored])

    seeds = int(seed_inventory.get(crop, 0))
    desired_seeds = worker_count * SEED_RESERVE_PER_WORKER
    buy_count = max(0, desired_seeds - seeds)
    seed_price = int(crop_specs[crop]["seed_price"])
    affordable = max(0, (money - MIN_CASH_RESERVE) // max(1, seed_price))
    buy_count = min(buy_count, affordable)
    if buy_count:
        market.append(["BUY_SEED", crop, buy_count])
        money -= seed_price * buy_count

    hires_today = int(me.get("hires_today", len(hands)))
    if len(hands) < HIRE_TARGET:
        cost = _hire_cost(hires_today)
        if money - cost >= MIN_CASH_RESERVE:
            market.append(["HIRE"])

    actions = _plan_workers(me, day, seeds, crop, crop_specs, int(obs.get("hour", 0)), int(obs.get("turns_per_day", 12)))
    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[:MAX_MARKET_ORDERS],
    }

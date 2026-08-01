"""Deterministic multi-worker Kaggriculture agent."""

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


def _plan_workers(me, day, seeds, crop, crop_specs):
    tiles = me["tiles"]
    workers = [me["farmer"]] + list(me.get("hands", []))
    candidates = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            priority = _task_priority(tile, day, crop_specs)
            if priority is not None:
                candidates.append((priority, y, x))

    remaining = set(range(len(candidates)))
    actions = []
    for position in workers:
        if not remaining:
            actions.append(["PASS"])
            continue
        px, py = position
        choice = min(
            remaining,
            key=lambda index: (
                candidates[index][0],
                abs(candidates[index][2] - px) + abs(candidates[index][1] - py),
                candidates[index][1],
                candidates[index][2],
            ),
        )
        remaining.remove(choice)
        _, ty, tx = candidates[choice]
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

    actions = _plan_workers(me, day, seeds, crop, crop_specs)
    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[:MAX_MARKET_ORDERS],
    }

"""Deterministic multi-worker Kaggriculture agent."""

HIRE_TARGET = 4
SEED_RESERVE_PER_WORKER = 2
MIN_CASH_RESERVE = 100
MAX_MARKET_ORDERS = 10


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


def _task_priority(tile, day):
    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        if int(tile.get("yield_units", 0)) > 0 or day - int(tile.get("planted_day", day)) >= 2:
            return 0
        if not tile.get("watered_today", False):
            return 1
        return None
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return 2
    if tile is None:
        return 3
    return None


def _action_at(tile, day, available_seeds):
    priority = _task_priority(tile, day)
    if priority == 0:
        return ["HARVEST"], available_seeds
    if priority == 1:
        return ["WATER"], available_seeds
    if priority == 2:
        return ["DIG"], available_seeds
    if priority == 3 and available_seeds > 0:
        return ["PLANT", "WHEAT"], available_seeds - 1
    return ["PASS"], available_seeds


def _plan_workers(me, day, seeds):
    tiles = me["tiles"]
    workers = [me["farmer"]] + list(me.get("hands", []))
    candidates = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            priority = _task_priority(tile, day)
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
            action, seeds = _action_at(tiles[ty][tx], day, seeds)
        else:
            action = _move(position, (tx, ty))
        actions.append(action)
    return actions


def agent(obs):
    me = obs["farms"][int(obs["player"])]
    private = obs["private"]
    day = int(obs.get("day", 0))
    hands = me.get("hands", [])
    worker_count = 1 + len(hands)

    market = []
    money = int(me["money"])
    stored = int(private.get("shed", {}).get("WHEAT", 0))
    if stored > 0:
        market.append(["SELL", "WHEAT", stored])

    seeds = int(private.get("seeds", {}).get("WHEAT", 0))
    desired_seeds = worker_count * SEED_RESERVE_PER_WORKER
    buy_count = max(0, desired_seeds - seeds)
    affordable = max(0, (money - MIN_CASH_RESERVE) // 10)
    buy_count = min(buy_count, affordable)
    if buy_count:
        market.append(["BUY_SEED", "WHEAT", buy_count])
        money -= 10 * buy_count

    hires_today = int(me.get("hires_today", len(hands)))
    if len(hands) < HIRE_TARGET:
        cost = _hire_cost(hires_today)
        if money - cost >= MIN_CASH_RESERVE:
            market.append(["HIRE"])

    actions = _plan_workers(me, day, seeds)
    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[:MAX_MARKET_ORDERS],
    }

"""Deterministic multi-worker Kaggriculture agent."""

from functools import lru_cache
from math import ceil

MIN_HAND_TARGET = 4
MAX_HAND_TARGET = 5
SEED_RESERVE_PER_WORKER = 2
MIN_CASH_RESERVE = 100
MAX_MARKET_ORDERS = 10
CROP_STRATEGY = "BEST_RETURN"
SELL_STRATEGY = "PRICE_AWARE"
ECONOMY_STRATEGY = "FINITE_HORIZON"
ROBUST_ONLINE_PLANNER = True
HISTORY_LIMIT = 48

DEFAULT_CROPS = {
    "WHEAT": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3, "fallback_price": 15},
}

_PUBLIC_HISTORY = []
_LAST_STEP = None


def _update_public_history(obs):
    """Keep a bounded, deterministic summary made only from public observations."""
    global _LAST_STEP
    step = int(obs.get("step", int(obs.get("day", 0)) * int(obs.get("turns_per_day", 24)) + int(obs.get("hour", 0))))
    if _LAST_STEP is None or step <= _LAST_STEP:
        _PUBLIC_HISTORY.clear()
    me = obs["farms"][int(obs["player"])]
    plants = [tile for row in me.get("tiles", []) for tile in row
              if isinstance(tile, dict) and tile.get("kind") == "PLANT"]
    weeds = sum(isinstance(tile, dict) and tile.get("kind") == "WEED"
                for row in me.get("tiles", []) for tile in row)
    _PUBLIC_HISTORY.append({
        "step": step,
        "prices": {str(crop): int(price) for crop, price in obs.get("market", {}).get("prices", {}).items()},
        "yields": {str(tile.get("crop", "WHEAT")): int(tile.get("yield_units", 0)) for tile in plants},
        "weeds": weeds,
    })
    del _PUBLIC_HISTORY[:-HISTORY_LIMIT]
    _LAST_STEP = step
    return tuple(_PUBLIC_HISTORY)


def _uncertainty_scenarios(crop, spec, history):
    """Return a small uncertainty set for a public-observation-only short rollout."""
    prices = [row["prices"][crop] for row in history if crop in row["prices"]]
    yields = [row["yields"][crop] for row in history if row["yields"].get(crop, 0) > 0]
    price = prices[-1] if prices else int(spec["fallback_price"])
    observed_yield = yields[-1] if yields else float(spec["expected_yield"])
    price_spread = max(prices) - min(prices) if len(prices) > 1 else max(1, price // 10)
    yield_spread = max(yields) - min(yields) if len(yields) > 1 else 1
    weed_pressure = max((row["weeds"] for row in history), default=0)
    return (
        (max(1, price - price_spread), max(1.0, observed_yield - yield_spread), weed_pressure),
        (price, max(1.0, observed_yield), weed_pressure),
        (price + price_spread, observed_yield + yield_spread, max(0, weed_pressure - 1)),
    )


def _robust_crop_value(crop, spec, day, total_days, history):
    """CVaR proxy: mean of the two worst bounded scenario returns."""
    harvests = _remaining_harvests(spec, day, total_days)
    values = sorted(
        harvests * (price * expected_yield - int(spec["seed_price"])) - weeds * int(spec["seed_price"])
        for price, expected_yield, weeds in _uncertainty_scenarios(crop, spec, history)
    )
    return sum(values[:2]) / min(2, len(values))


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
                future_cost[0] + conflict,
                future_cost[1] + overdue,
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
    # A later worker may approach a different task through the same intermediate
    # cell. Resolve that one-turn collision deterministically after assignment.
    reserved_moves = set()
    for index, (position, action) in enumerate(zip(workers, actions)):
        if action[0] not in {"NORTH", "SOUTH", "EAST", "WEST"}:
            continue
        destination = _next_position(position, action)
        if destination in reserved_moves:
            actions[index] = ["PASS"]
        else:
            reserved_moves.add(destination)
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


def _remaining_harvests(spec, day, total_days):
    maturity = max(1, int(spec["maturity_days"]))
    return max(0, (total_days - day - 1) // maturity)


def _hand_target(me, harvests_left):
    """Scale labor to observed cultivable capacity without hiring for a spent season."""
    if harvests_left <= 0:
        return 0
    usable_tiles = sum(tile != "LOCKED" for row in me["tiles"] for tile in row)
    capacity_target = ceil(usable_tiles / 6) - 1
    return max(MIN_HAND_TARGET, min(MAX_HAND_TARGET, capacity_target))


def _future_prices(spec, day, current_price):
    forecast = spec.get("price_forecast", [])
    if isinstance(forecast, list) and forecast:
        return [int(value) for value in forecast[day:] if isinstance(value, (int, float))]
    return [current_price]


def _choose_crop(obs, seeds, history=()):
    specs = _crop_specs(obs)
    prices = obs.get("market", {}).get("prices", {})
    known = [crop for crop in specs if int(seeds.get(crop, 0)) > 0 or crop in prices]
    if not known or CROP_STRATEGY == "WHEAT_ONLY":
        return "WHEAT", specs

    day = int(obs.get("day", 0))
    total_days = int(obs.get("total_days", 12))

    if ROBUST_ONLINE_PLANNER and history:
        return max(known, key=lambda crop: (_robust_crop_value(crop, specs[crop], day, total_days, history), crop)), specs

    def daily_return(crop):
        spec = specs[crop]
        sale = int(prices.get(crop, spec["fallback_price"]))
        if ECONOMY_STRATEGY == "FINITE_HORIZON":
            harvests = _remaining_harvests(spec, day, total_days)
            sale = max(_future_prices(spec, day, sale))
            margin = sale * float(spec["expected_yield"]) - int(spec["seed_price"])
            return harvests * margin, harvests, margin, crop
        margin = sale * float(spec["expected_yield"]) - int(spec["seed_price"])
        return margin / max(1, int(spec["maturity_days"])), margin, crop

    return max(known, key=daily_return), specs


def agent(obs):
    history = _update_public_history(obs) if ROBUST_ONLINE_PLANNER else ()
    me = obs["farms"][int(obs["player"])]
    private = obs["private"]
    day = int(obs.get("day", 0))
    # The public competition horizon is known a priori; shifted evaluators may
    # supply an explicit horizon, but no private/future field is consulted.
    total_days = int(obs.get("total_days", 30 if ROBUST_ONLINE_PLANNER else 12))
    hands = me.get("hands", [])
    worker_count = 1 + len(hands)

    market = []
    money = int(me["money"])
    seed_inventory = private.get("seeds", {})
    crop, crop_specs = _choose_crop({**obs, "total_days": total_days}, seed_inventory, history)
    prices = obs.get("market", {}).get("prices", {})
    stored_inventory = private.get("shed", {})
    for stored_crop in sorted(crop_specs):
        stored = int(stored_inventory.get(stored_crop, 0))
        price = int(prices.get(stored_crop, crop_specs[stored_crop]["fallback_price"]))
        target = int(crop_specs[stored_crop].get("sell_above", crop_specs[stored_crop]["fallback_price"]))
        future_peak = max(_future_prices(crop_specs[stored_crop], day, price))
        final_day = day >= total_days - 1
        if stored > 0 and (SELL_STRATEGY == "IMMEDIATE" or price >= max(target, future_peak) or final_day):
            market.append(["SELL", stored_crop, stored])

    seeds = int(seed_inventory.get(crop, 0))
    harvests_left = _remaining_harvests(crop_specs[crop], day, total_days)
    desired_seeds = worker_count * SEED_RESERVE_PER_WORKER if harvests_left else 0
    buy_count = max(0, desired_seeds - seeds)
    seed_price = int(crop_specs[crop]["seed_price"])
    affordable = max(0, (money - MIN_CASH_RESERVE) // max(1, seed_price))
    buy_count = min(buy_count, affordable)
    if buy_count:
        market.append(["BUY_SEED", crop, buy_count])
        money -= seed_price * buy_count

    hires_today = int(me.get("hires_today", len(hands)))
    future_sale = max(_future_prices(crop_specs[crop], day, int(prices.get(crop, crop_specs[crop]["fallback_price"]))))
    expected_crop_margin = future_sale * float(crop_specs[crop]["expected_yield"]) - seed_price
    hand_target = _hand_target(me, harvests_left)
    if len(hands) < hand_target:
        cost = _hire_cost(hires_today)
        if money - cost >= MIN_CASH_RESERVE and expected_crop_margin * harvests_left > cost:
            market.append(["HIRE"])

    actions = _plan_workers(me, day, seeds, crop, crop_specs, int(obs.get("hour", 0)), int(obs.get("turns_per_day", 12)))
    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[:MAX_MARKET_ORDERS],
    }

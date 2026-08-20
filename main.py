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
OPPONENT_AWARE_POLICY = True
LONG_HORIZON_MIXED_FARM_ROUTE = False
HISTORY_LIMIT = 48

# Logic-distilled from COK-ZhangZiliang/Kaggriculture@58c91c3 (Apache-2.0).
# The source agent uses a fixed action trace; this implementation retains only
# its portable, observation-driven economic route and no trace or weights.
MIXED_FARM_ROUTE_SOURCE = {
    "url": "https://github.com/COK-ZhangZiliang/Kaggriculture",
    "commit": "58c91c390f1cf8b3cace8c078c00b938bae398ff",
    "license": "Apache-2.0",
    "artifact_sha256": "7ce060d8551cf3e7a20a800c1eea2e18ece63d6d6eab8e21199b65f9b78e4794",
}
MIXED_FARM_ROUTE_FIRES = 0

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


def _mixed_farm_route(obs, specs, seeds):
    """Build a bounded long-horizon route from public state only.

    Wheat is the opening crop and feed reserve, melon gets one bounded capital
    window, and strawberry is preferred only when recurring harvests remain.
    Land, hand, and herd orders are gated by explicit runtime capabilities so
    compact/offline contracts never receive speculative actions.
    """
    global MIXED_FARM_ROUTE_FIRES
    MIXED_FARM_ROUTE_FIRES += 1
    day = max(0, int(obs.get("day", 0)))
    total_days = max(1, int(obs.get("total_days", 30)))
    progress = min(1.0, day / total_days)
    prices = obs.get("market", {}).get("prices", {})
    available = set(specs) & (set(prices) | set(seeds))
    realizable = {
        crop for crop in available
        if _remaining_harvests(specs[crop], day, total_days) > 0
    }
    crop = "WHEAT" if "WHEAT" in realizable else None
    if progress >= 0.42 and "STRAWBERRY" in realizable:
        crop = "STRAWBERRY"
    elif 0.20 <= progress < 0.52 and "MELON" in realizable:
        crop = "MELON"
    if crop is None and realizable:
        crop = max(realizable, key=lambda item: (
            _remaining_harvests(specs[item], day, total_days)
            * (int(prices.get(item, specs[item]["fallback_price"]))
               * float(specs[item]["expected_yield"]) - int(specs[item]["seed_price"])),
            item,
        ))
    crop = crop or "WHEAT"

    capabilities = set(obs.get("capabilities", ()))
    money = int(obs["farms"][int(obs["player"])].get("money", 0))
    orders = []
    if "BUY_LAND" in capabilities and progress < 0.35 and money >= 1800:
        orders.append(["BUY_LAND"])
    animals = obs.get("animals", {})
    if "BUY_ANIMAL" in capabilities and 0.28 <= progress < 0.72:
        herd = sum(int(value) for value in obs.get("private", {}).get("animals", {}).values())
        for animal in ("CHICKEN", "COW", "SHEEP"):
            spec = animals.get(animal, {})
            cost = int(spec.get("price", 0))
            if herd < 3 and cost > 0 and money - cost >= 600:
                orders.append(["BUY_ANIMAL", animal, 1])
                break
    return {"crop": crop, "feed_reserve": 3 if animals else 0, "market": orders}


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
        remaining = [int(value) for value in forecast[day:] if isinstance(value, (int, float))]
        return remaining or [current_price]
    return [current_price]


def _scarcity_pressure(obs, crop):
    """Summarize competition using only public farms and shared market state.

    The aggregate deliberately ignores opponent ordering and every ``private``
    object.  Values are bounded so unexpected public observations cannot cause
    unbounded purchases.
    """
    player = int(obs.get("player", 0))
    opponents = [farm for index, farm in enumerate(obs.get("farms", [])) if index != player]
    market = obs.get("market", {})
    inventory = max(0, int(market.get("inventory", {}).get(crop, 10000)))
    anchor = max(1, int(market.get("inventory_anchor", {}).get(crop, 10000)))
    inventory_pressure = max(0.0, min(1.0, (anchor - inventory) / anchor))
    if not opponents:
        return {"inventory": inventory_pressure, "labor": 0.0, "field_demand": 0.0,
                "cash": 0.0, "total": inventory_pressure}
    labor = sum(len(farm.get("hands", [])) for farm in opponents) / (len(opponents) * MAX_HAND_TARGET)
    open_tiles = occupied_tiles = 0
    my_cash = int(obs.get("farms", [{}])[player].get("money", 0))
    richer = 0
    for farm in opponents:
        richer += int(int(farm.get("money", 0)) >= my_cash)
        for row in farm.get("tiles", []):
            for tile in row:
                if tile != "LOCKED":
                    open_tiles += 1
                    occupied_tiles += int(isinstance(tile, dict) and tile.get("kind") == "PLANT")
    field_demand = occupied_tiles / max(1, open_tiles)
    cash = richer / len(opponents)
    values = {
        "inventory": inventory_pressure,
        "labor": max(0.0, min(1.0, labor)),
        "field_demand": max(0.0, min(1.0, field_demand)),
        "cash": cash,
    }
    values["total"] = sum(values.values()) / 4
    return values


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
    mixed_route = None
    if LONG_HORIZON_MIXED_FARM_ROUTE:
        mixed_route = _mixed_farm_route({**obs, "total_days": total_days}, crop_specs, seed_inventory)
        crop = mixed_route["crop"]
    prices = obs.get("market", {}).get("prices", {})
    stored_inventory = private.get("shed", {})
    pressure = _scarcity_pressure(obs, crop) if OPPONENT_AWARE_POLICY else {
        "inventory": 0.0, "labor": 0.0, "field_demand": 0.0, "cash": 0.0, "total": 0.0
    }
    for stored_crop in sorted(crop_specs):
        stored = int(stored_inventory.get(stored_crop, 0))
        price = int(prices.get(stored_crop, crop_specs[stored_crop]["fallback_price"]))
        target = int(crop_specs[stored_crop].get("sell_above", crop_specs[stored_crop]["fallback_price"]))
        future_peak = max(_future_prices(crop_specs[stored_crop], day, price))
        final_day = day >= total_days - 1
        crowded_sale = pressure["inventory"] >= 0.25 and price >= target
        reserved = mixed_route["feed_reserve"] if mixed_route and stored_crop == "WHEAT" else 0
        sellable = max(0, stored - reserved)
        if sellable > 0 and (SELL_STRATEGY == "IMMEDIATE" or price >= max(target, future_peak) or final_day or crowded_sale):
            market.append(["SELL", stored_crop, sellable])

    if mixed_route:
        market.extend(mixed_route["market"])

    seeds = int(seed_inventory.get(crop, 0))
    harvests_left = _remaining_harvests(crop_specs[crop], day, total_days)
    advance_reserve = 1 if pressure["labor"] + pressure["field_demand"] >= 0.75 else 0
    desired_seeds = worker_count * SEED_RESERVE_PER_WORKER + advance_reserve if harvests_left else 0
    buy_count = max(0, desired_seeds - seeds)
    seed_price = int(crop_specs[crop]["seed_price"])
    affordable = max(0, (money - MIN_CASH_RESERVE) // max(1, seed_price))
    # When the shared crop stock is already depleted, preserve cash and avoid
    # joining a crowded buy queue; one reserve unit still keeps planting live.
    if pressure["inventory"] >= 0.6:
        buy_count = min(buy_count, max(0, 1 - seeds))
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
        opportunity = expected_crop_margin * harvests_left * (1 + pressure["field_demand"])
        if money - cost >= MIN_CASH_RESERVE and opportunity > cost:
            market.append(["HIRE"])

    actions = _plan_workers(me, day, seeds, crop, crop_specs, int(obs.get("hour", 0)), int(obs.get("turns_per_day", 12)))
    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[:MAX_MARKET_ORDERS],
    }

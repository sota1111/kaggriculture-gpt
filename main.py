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
PUBLIC_SCHEDULER_COMPONENT = True
MULTI_STOP_TASK_BUNDLING = True
PROJECTED_MARKET_EXECUTION = False
FERTILIZER_COVERAGE = True
FERTILIZER_CONSTRAINED_PRODUCTION = False
STAGGERED_STRAWBERRY_RENEWAL = True
CARE_LIVESTOCK_COMPONENT = True
FEED_ECONOMIC_DECISION = False
SHED_OVERFLOW_PROTECTION = True
CASH_RUNWAY_ACREAGE_EXPANSION = False
PRODUCTIVE_ACTION_CAPACITY = False
CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER = False
PUBLIC_SHOP_PREFIX_ROUTE_SELECTOR = False
COMPACT_REPLAY_POLICY = False
SEQUENCE_PRECURSOR_POLICY = False
RECEDING_HORIZON_SEQUENCE_PLANNER = False
LAYOUT_AWARE_PRODUCTION_ARCHITECTURE = False
V21_ONE_TIME_LATE_CAPITAL_LATCH = False
MOON_V56_TOMATO_SCARCITY_FORK = False
PUBLIC_STEP0_WHEAT_MARKET_LEAD = True
SEQUENCE_PLANNER_HORIZON = 3
HISTORY_LIMIT = 48

# Deterministically distilled from the SOT-2824 screen split only.  These
# constants capture a state-conditioned production cadence; they contain no
# replay actions, episode identity, or external model weights.
COMPACT_REPLAY_POLICY_CONSTANTS = {
    "teacher_dataset_sha256": "c2807cd6f38f5a69201939f973114310e89a64dd000e34fce9bf372ba068348f",
    "hands_per_unlocked_quadrant": (4, 8, 12),
    "land_milestones": ((5, 2, 2), (8, 8, 3)),
}

# Logic-distilled from COK-ZhangZiliang/Kaggriculture@58c91c3 (Apache-2.0).
# The source agent uses a fixed action trace; this implementation retains only
# its portable, observation-driven economic route and no trace or weights.
MIXED_FARM_ROUTE_SOURCE = {
    "url": "https://github.com/COK-ZhangZiliang/Kaggriculture",
    "commit": "58c91c390f1cf8b3cace8c078c00b938bae398ff",
    "license": "Apache-2.0",
    "artifact_sha256": "7ce060d8551cf3e7a20a800c1eea2e18ece63d6d6eab8e21199b65f9b78e4794",
}
PUBLIC_EXECUTION_SOURCES = {
    "scheduler": {
        "url": "https://github.com/lonespear/kaggriculture",
        "commit": "774b26055e22f0e809464f1d8bf65d6e8172af0e",
        "license": "MIT",
    },
    "task_bundling": {
        "url": "https://github.com/lonespear/kaggriculture",
        "commit": "774b26093ccf4246525517d48420349b841b6e50",
        "license": "MIT",
    },
    "strawberry_renewal": {
        "url": "https://github.com/lonespear/kaggriculture",
        "commit": "774b26093ccf4246525517d48420349b841b6e50",
        "license": "MIT",
    },
    "market": {
        "url": "https://github.com/COK-ZhangZiliang/Kaggriculture",
        "commit": "58c91c390f1cf8b3cace8c078c00b938bae398ff",
        "license": "Apache-2.0",
    },
    "care_livestock": {
        "url": "https://github.com/lonespear/kaggriculture",
        "commit": "774b26055e22f0e809464f1d8bf65d6e8172af0e",
        "license": "MIT",
        "boundary": "public-state unit economics only; no fixed route, replay trace, or weights",
    },
    "feed_economic": {
        "url": "https://github.com/zansued/kaggriculture-ai-agent",
        "commit": "9de2779147c004ab9e7b1545cd62ace4ef7ad1cd",
        "license": "MIT",
        "boundary": "current own livestock/feed/wheat/cash plus public shop demand; no schedule, trace, replay bytes, identity, seed, or weights",
    },
    "shed_overflow": {
        "url": "https://github.com/lonespear/kaggriculture",
        "commit": "774b26055e22f0e809464f1d8bf65d6e8172af0e",
        "license": "MIT",
        "boundary": "capacity/clock/own-inventory logistics only; no projected market or terminal recovery",
    },
    "runway_acreage": {
        "url": "https://github.com/Seyamalam/Kaggriculture",
        "commit": "8b8c421eb10634c756583ce10c75189f50c83a72",
        "license": "MIT",
        "artifact_sha256": "0cd14b653102d276c4f902fa3b8c6bd81d869b8ab64c422cb881b9d2346ec639",
        "boundary": "public cash/runway staging only; no fixed quadrant, crop block, hand route, replay trace, or weights",
    },
    "productive_action_capacity": {
        "url": "https://github.com/lonespear/kaggriculture",
        "commit": "774b26055e22f0e809464f1d8bf65d6e8172af0e",
        "license": "MIT",
        "boundary": "public worker positions and crop-service backlog only; no fixed route, replay trace, private inventory, or weights",
    },
    "capacity_dispatcher": {
        "url": "https://github.com/lonespear/kaggriculture",
        "commit": "774b26055e22f0e809464f1d8bf65d6e8172af0e",
        "license": "MIT",
        "boundary": "current public clock, visible tasks, and worker positions only; no fixed trace, future state, private inventory, or weights",
    },
    "shop_prefix_route_selector": {
        "url": "https://github.com/COK-ZhangZiliang/Kaggriculture",
        "commit": "58c91c390f1cf8b3cace8c078c00b938bae398ff",
        "license": "Apache-2.0",
        "artifact_sha256": "7ce060d8551cf3e7a20a800c1eea2e18ece63d6d6eab8e21199b65f9b78e4794",
        "boundary": "first three public unlocked shops only; no route trace, identity, episode, submission, seed, or private state",
    },
    "v21_late_capital_latch": {
        "url": "https://github.com/Seyamalam/Kaggriculture",
        "commit": "8b8c421eb10634c756583ce10c75189f50c83a72",
        "license": "MIT",
        "artifact_sha256": "0cd14b653102d276c4f902fa3b8c6bd81d869b8ab64c422cb881b9d2346ec639",
        "boundary": "one decision from step/player/both public bank values; no fixed route, identity, seed, private state, or future data",
    },
    "moon_v56_tomato_scarcity": {
        "url": "https://www.kaggle.com/code/prvsiyan/kaggriculture-frontier-the-moon-counts-melons",
        "notebook_version": 56,
        "notebook_sha256": "97be5f16511523daec1de44bc533e385353cc4e7d2170e88a6a4f31a123c5b5f",
        "agent_sha256": "d2f51ca8851e563e3b8d24aeda28ff358bfdb8901039a89c39ff2e75aac68179",
        "license": "not-declared-in-downloaded-notebook-metadata",
        "boundary": "first three public shops, public clock, own visible tiles/actions, and own inventory only; no opponent private state, replay identity, seed, future outcome, fixed full route, or submission",
    },
    "public_step0_wheat_market_lead": {
        "url": "https://www.kaggle.com/code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta",
        "kernel_id": 129396610,
        "version": "current public snapshot acquired 2026-08-21",
        "notebook_sha256": "a7447511510ed22b73f2315246b6bf4de66f219ffe3ba692a377f3fb47931331",
        "agent_sha256": "489f5d197527f107027626cce79d850fd2ca90edd43d94384b849b6511e27bdb",
        "license": "not declared; behavior independently reimplemented from public action telemetry",
        "boundary": "step/player, own public cash, and public WHEAT price only; inserts one five-WHEAT market order, with no source code, route, replay bytes, identity, seed, private/future state, or weights",
    },
    "sequence_precursor": {
        "evidence": "docs/measurements/SOT-2835/SOT-2836-winner-sequence-support.json",
        "sources": ("lonespear", "COK-ZhangZiliang", "Seyamalam"),
        "boundary": "bounded early pasture task/location sequence from current public farm state; no action trace, identity, seed, private inventory, or weights",
    },
}
MIXED_FARM_ROUTE_FIRES = 0
PUBLIC_SCHEDULER_FIRES = 0
MULTI_STOP_TASK_BUNDLE_FIRES = 0
PROJECTED_MARKET_FIRES = 0
FERTILIZER_COVERAGE_FIRES = 0
FERTILIZER_CONSTRAINED_PRODUCTION_FIRES = 0
FERTILIZER_CONSTRAINED_PRODUCTION_TELEMETRY = {
    "plans": 0, "demand_caps": 0, "supply_caps": 0, "action_caps": 0,
    "cash_caps": 0, "shed_caps": 0, "last_plan": {},
}
STAGGERED_STRAWBERRY_RENEWAL_FIRES = 0
CARE_LIVESTOCK_FIRES = 0
FEED_ECONOMIC_FIRES = 0
SHED_OVERFLOW_FIRES = 0
CASH_RUNWAY_ACREAGE_FIRES = 0
PRODUCTIVE_ACTION_CAPACITY_FIRES = 0
CAPACITY_DISPATCHER_FIRES = 0
CAPACITY_DISPATCHER_TELEMETRY = {
    "turns": 0, "standing": 0, "productive_assignments": 0,
    "travel_steps": 0, "budget_repairs": 0, "tier_assignments": {},
    "last_tier_budgets": {}, "last_travel_budget": 0,
}
PUBLIC_SHOP_PREFIX_ROUTE_FIRES = {
    "yarn_first": 0, "yarn_second": 0, "yarn_third": 0,
    "early_milk_support": 0, "default": 0,
}
COMPACT_REPLAY_POLICY_FIRES = {"land": 0, "labor": 0}
SEQUENCE_PRECURSOR_POLICY_FIRES = 0
SEQUENCE_PRECURSOR_ECONOMIC_REACHED = 0
SEQUENCE_PLANNER_FIRES = 0
SEQUENCE_PLANNER_REPAIRS = 0
SEQUENCE_PLANNER_MULTI_STEP_FIRES = 0
LAYOUT_AWARE_PRODUCTION_FIRES = 0
LAYOUT_AWARE_PRODUCTION_TELEMETRY = {
    "demand_caps": 0, "shed_weighted_assignments": 0, "pasture_placements": 0,
    "last_plan": {},
}
V21_LATE_CAPITAL_LATCH_STATE = {}
V21_LATE_CAPITAL_LATCH_DECISIONS = []
V21_LATE_CAPITAL_LATCH_FIRES = 0
V21_LATE_CAPITAL_SUPPRESSED_ORDERS = 0
MOON_V56_TOMATO_SCARCITY_FIRES = {
    "trigger": 0, "seed_relay": 0, "plant": 0, "harvest": 0, "terminal_sale": 0,
}
PUBLIC_STEP0_WHEAT_MARKET_LEAD_FIRES = {0: 0, 1: 0}
_MOON_V56_TOMATO_STATE = {
    0: {"last_step": -1, "active": False, "seed_debt": 0, "plants": 0, "harvests": 0},
    1: {"last_step": -1, "active": False, "seed_debt": 0, "plants": 0, "harvests": 0},
}
MOON_V56_TOMATO_TARGET = 3
MOON_V56_TRIGGER_STEP = 216
MOON_V56_SEED_STEP = 264
MOON_V56_RELAY_LIMIT = 8
MOON_V56_PLANT_WINDOW = (271, 286)
MOON_V56_TERMINAL_STEP = 708
V21_LATE_CAPITAL_START_STEP = 577
V21_LATE_CAPITAL_LEAD_THRESHOLD = 5000
V21_CAPITAL_ORDER_TYPES = frozenset({
    "BUY_SEED", "HIRE", "BUY_LAND", "BUY_ANIMAL", "BUY_PRODUCT",
})

_MILK_SUPPORT_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
_SHOP_PREFIX_ROUTES = {
    "yarn_first": {"cow_target": 6, "sheep_target": 12, "crop": "WHEAT"},
    "yarn_second": {"cow_target": 6, "sheep_target": 12, "crop": "WHEAT"},
    "yarn_third": {"cow_target": 6, "sheep_target": 8, "crop": "WHEAT"},
    "early_milk_support": {"cow_target": 10, "sheep_target": 4, "crop": "STRAWBERRY"},
    "default": {"cow_target": 8, "sheep_target": 6, "crop": "STRAWBERRY"},
}

DEFAULT_CROPS = {
    "WHEAT": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3, "fallback_price": 15},
}

_PUBLIC_HISTORY = []
_LAST_STEP = None
_SEQUENCE_PRECURSOR_STATE = {
    "phase": "idle", "started_step": None, "fired": False,
    "public_inventory": (),
}
_SEQUENCE_PLANNER_STATE = {"last_step": None, "last_signature": (), "streak": 0}


def _sequence_planner_actions(obs, baseline, crop, crop_specs):
    """Choose the first action of a bounded task sequence and replan each turn.

    Search inputs are limited to the current observation: own visible tiles and
    locations, current own resources, the shared market and the public clock.
    No replay identity, future state, fixed action trace, or external weights
    enter the score.  Resource feasibility is checked before a candidate may
    replace the one-step scheduler action.
    """
    global SEQUENCE_PLANNER_FIRES, SEQUENCE_PLANNER_REPAIRS
    global SEQUENCE_PLANNER_MULTI_STEP_FIRES
    if not RECEDING_HORIZON_SEQUENCE_PLANNER:
        return baseline
    me = obs["farms"][int(obs["player"])]
    tiles = me.get("tiles", [])
    workers = [me.get("farmer", [0, 0]), *me.get("hands", [])]
    private = obs.get("private", {})
    inventories = list(private.get("inventories", ()))
    seeds = max(0, int(private.get("seeds", {}).get(crop, 0)))
    fertilizer = sum(max(0, int(row.get("FERTILIZER", 0)))
                     for row in inventories if isinstance(row, dict))
    shed = private.get("shed", {}) if isinstance(private.get("shed", {}), dict) else {}
    shed_capacity = max(0, int(me.get("shed_capacity", 100)))
    shed_used = sum(max(0, int(value)) for value in shed.values())
    step = int(obs.get("step", int(obs.get("day", 0)) * int(obs.get("turns_per_day", 24))
                              + int(obs.get("hour", 0))))
    total_steps = int(obs.get("total_days", 30)) * int(obs.get("turns_per_day", 24))
    remaining = max(0, total_steps - step)
    day = int(obs.get("day", 0))

    tasks = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            priority = _task_priority(tile, day, crop_specs, fertilizer)
            if priority is None:
                continue
            # Hard resource and remaining-horizon constraints.
            if priority == 4 and (seeds <= 0 or remaining < 2):
                continue
            if priority == 1 and fertilizer <= 0:
                continue
            if priority == 0 and shed_used >= shed_capacity:
                continue
            tasks.append((priority, y, x))
    tasks.sort()
    if not tasks or not workers:
        return baseline

    def tail_cost(first_index, start):
        """Two additional stops: bounded multi-stop bundling, deterministic."""
        _, fy, fx = tasks[first_index]
        unused = [task for index, task in enumerate(tasks) if index != first_index]
        cursor = (fx, fy)
        cost = 0
        for _ in range(max(0, SEQUENCE_PLANNER_HORIZON - 1)):
            if not unused:
                break
            choice = min(unused, key=lambda task: (
                task[0], abs(task[2] - cursor[0]) + abs(task[1] - cursor[1]),
                task[1], task[2]))
            cost += abs(choice[2] - cursor[0]) + abs(choice[1] - cursor[1])
            cursor = (choice[2], choice[1])
            unused.remove(choice)
        return cost

    proposals = []
    for worker_index, position in enumerate(workers):
        px, py = int(position[0]), int(position[1])
        for task_index, (priority, ty, tx) in enumerate(tasks):
            distance = abs(tx - px) + abs(ty - py)
            # Travel and labor/action capacity: the first task must be reachable
            # within the remaining horizon and one worker receives one action.
            if distance + 1 > remaining:
                continue
            proposals.append((priority * 100 + distance * 4 + tail_cost(task_index, (px, py)),
                              ty, tx, worker_index, task_index))
    if not proposals:
        return baseline

    amended = list(baseline)
    used_workers, used_tasks, reserved = set(), set(), set()
    chosen_signature = []
    seed_budget, fertilizer_budget, shed_budget = seeds, fertilizer, shed_capacity - shed_used
    for _, ty, tx, worker_index, task_index in sorted(proposals):
        if worker_index in used_workers or task_index in used_tasks:
            continue
        priority = tasks[task_index][0]
        if priority == 4 and seed_budget <= 0:
            continue
        if priority == 1 and fertilizer_budget <= 0:
            continue
        if priority == 0 and shed_budget <= 0:
            continue
        position = tuple(workers[worker_index])
        action = (_move(position, (tx, ty)) if position != (tx, ty)
                  else _action_at(tiles[ty][tx], day, seed_budget, crop, crop_specs,
                                  fertilizer_budget)[0])
        destination = _next_position(position, action)
        if action[0] in {"NORTH", "SOUTH", "EAST", "WEST"} and destination in reserved:
            continue
        if action[0] == "PLANT":
            seed_budget -= 1
        elif action[0] == "FERTILIZE":
            fertilizer_budget -= 1
        elif action[0] == "HARVEST":
            shed_budget -= 1
        amended[worker_index] = action
        used_workers.add(worker_index)
        used_tasks.add(task_index)
        reserved.add(destination)
        chosen_signature.append((worker_index, ty, tx, action[0]))

    signature = tuple(chosen_signature)
    state = _SEQUENCE_PLANNER_STATE
    if state["last_step"] is not None and step > state["last_step"]:
        if signature and signature != state["last_signature"]:
            SEQUENCE_PLANNER_REPAIRS += 1
        state["streak"] = state["streak"] + 1 if signature else 0
    else:
        state["streak"] = int(bool(signature))
    state.update({"last_step": step, "last_signature": signature})
    if amended != baseline:
        SEQUENCE_PLANNER_FIRES += 1
        if state["streak"] >= 2:
            SEQUENCE_PLANNER_MULTI_STEP_FIRES += 1
    return amended


def _sequence_precursor_actions(obs, actions):
    """Distill the SOT-2836 early-pasture precursor into a bounded policy.

    The state machine is deliberately narrower than an economic threshold: it
    first recognizes the public task state (one existing pasture, no visible
    animals), then chooses a public empty location adjacent to that pasture,
    approaches it, and finally emits one BUILD_PASTURE action.  It expires
    after a short public-clock window and never inspects private inventory.
    """
    global SEQUENCE_PRECURSOR_POLICY_FIRES, SEQUENCE_PRECURSOR_ECONOMIC_REACHED
    if not SEQUENCE_PRECURSOR_POLICY:
        return actions
    step = int(obs.get("step", int(obs.get("day", 0)) * int(obs.get("turns_per_day", 24))
                              + int(obs.get("hour", 0))))
    me = obs["farms"][int(obs["player"])]
    tiles = me.get("tiles", [])
    workers = [me.get("farmer", [0, 0]), *me.get("hands", [])]
    pastures, visible_animals = [], 0
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get("kind") == "PASTURE":
                pastures.append((x, y))
            if isinstance(tile, dict) and tile.get("kind") in {"ANIMAL", "COW", "SHEEP", "CHICKEN"}:
                visible_animals += 1

    state = _SEQUENCE_PRECURSOR_STATE
    if state["phase"] == "idle":
        # SOT-2836 reproduced this task boundary in both panels.  Worker/cash
        # bands were contextual, so neither is fitted as a trigger.
        if step <= int(obs.get("turns_per_day", 24)) and len(pastures) == 1 and visible_animals == 0:
            public_inventory = tuple(sorted(
                (str(item), max(0, int(amount)))
                for item, amount in obs.get("market", {}).get("inventory", {}).items()
            ))
            state.update({"phase": "approach", "started_step": step, "fired": False,
                          "public_inventory": public_inventory})
        else:
            return actions
    if state["fired"] or step - int(state["started_step"]) > 8:
        state["phase"] = "expired"
        return actions

    px, py = pastures[0]
    adjacent = sorted(
        (x, y) for x, y in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1))
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) and tiles[y][x] is None
    )
    if not adjacent:
        state["phase"] = "expired"
        return actions
    proposals = []
    for worker_index, position in enumerate(workers):
        for target in adjacent:
            distance = abs(int(position[0]) - target[0]) + abs(int(position[1]) - target[1])
            proposals.append((distance, target[1], target[0], worker_index, target))
    _, _, _, worker_index, target = min(proposals)
    amended = list(actions)
    position = tuple(workers[worker_index])
    if position == target:
        amended[worker_index] = ["BUILD_PASTURE"]
        state.update({"phase": "economic_reached", "fired": True})
        SEQUENCE_PRECURSOR_POLICY_FIRES += 1
        SEQUENCE_PRECURSOR_ECONOMIC_REACHED += 1
    else:
        amended[worker_index] = _move(position, target)
        state["phase"] = "approach"
    return amended


def _public_shop_prefix_route(obs, record=False):
    """Select a production route from the first three public shops only."""
    shops = list(obs.get("town", {}).get("unlocked_shops", ()) or ())[:3]
    if shops[:1] == ["YARN_STORE"]:
        label = "yarn_first"
    elif "YARN_STORE" in shops[:2]:
        label = "yarn_second"
    elif "YARN_STORE" in shops:
        label = "yarn_third"
    elif _MILK_SUPPORT_SHOPS.intersection(shops):
        label = "early_milk_support"
    else:
        label = "default"
    if record:
        PUBLIC_SHOP_PREFIX_ROUTE_FIRES[label] += 1
    return label, dict(_SHOP_PREFIX_ROUTES[label])


def _update_public_history(obs):
    """Keep a bounded, deterministic summary made only from public observations."""
    global _LAST_STEP
    step = int(obs.get("step", int(obs.get("day", 0)) * int(obs.get("turns_per_day", 24)) + int(obs.get("hour", 0))))
    if _LAST_STEP is None or step <= _LAST_STEP:
        _PUBLIC_HISTORY.clear()
        _SEQUENCE_PRECURSOR_STATE.update({
            "phase": "idle", "started_step": None, "fired": False,
            "public_inventory": (),
        })
        _SEQUENCE_PLANNER_STATE.update(
            {"last_step": None, "last_signature": (), "streak": 0})
    me = obs["farms"][int(obs["player"])]
    plants = [tile for row in me.get("tiles", []) for tile in row
              if isinstance(tile, dict) and tile.get("kind") == "PLANT"]
    weeds = sum(isinstance(tile, dict) and tile.get("kind") == "WEED"
                for row in me.get("tiles", []) for tile in row)
    workers = [me.get("farmer", [0, 0]), *me.get("hands", [])]
    backlog = {"water": 0, "harvest": 0, "fertilize": 0}
    day = int(obs.get("day", 0))
    specs = _crop_specs(obs)
    for tile in plants:
        crop = tile.get("crop", "WHEAT")
        maturity = int(specs.get(crop, DEFAULT_CROPS["WHEAT"]).get("maturity_days", 2))
        if int(tile.get("yield_units", 0)) > 0 or day - int(tile.get("planted_day", day)) >= maturity:
            backlog["harvest"] += 1
        elif crop == "STRAWBERRY" and int(tile.get("fertilized_until_day", day)) < day:
            backlog["fertilize"] += 1
        elif not tile.get("watered_today", False):
            backlog["water"] += 1
    _PUBLIC_HISTORY.append({
        "step": step,
        "prices": {str(crop): int(price) for crop, price in obs.get("market", {}).get("prices", {}).items()},
        "yields": {str(tile.get("crop", "WHEAT")): int(tile.get("yield_units", 0)) for tile in plants},
        "weeds": weeds,
        "workers": tuple(tuple(int(value) for value in worker[:2]) for worker in workers),
        "backlog": backlog,
        "acreage": len(plants),
    })
    del _PUBLIC_HISTORY[:-HISTORY_LIMIT]
    _LAST_STEP = step
    return tuple(_PUBLIC_HISTORY)


def _productive_capacity_limit(obs, history):
    """Estimate maintainable acreage from public service throughput/backlog.

    Completed WATER/HARVEST/FERTILIZE demand is inferred conservatively from
    decreases between consecutive public tile snapshots. Worker displacement
    supplies the travel cost. The result only caps new planting/expansion; the
    existing scheduler continues to select and execute every worker action.
    """
    global PRODUCTIVE_ACTION_CAPACITY_FIRES
    me = obs["farms"][int(obs["player"])]
    workers = max(1, 1 + len(me.get("hands", [])))
    rows = list(history)[-min(HISTORY_LIMIT, int(obs.get("turns_per_day", 24))):]
    completed = 0
    distance = 0
    for before, after in zip(rows, rows[1:]):
        completed += sum(max(0, int(before["backlog"][name]) - int(after["backlog"][name]))
                         for name in ("water", "harvest", "fertilize"))
        distance += sum(abs(ax - bx) + abs(ay - by)
                        for (bx, by), (ax, ay) in zip(before["workers"], after["workers"]))
    current = rows[-1] if rows else {"backlog": {}, "acreage": 0}
    backlog = sum(int(current["backlog"].get(name, 0))
                  for name in ("water", "harvest", "fertilize"))
    # Before enough transitions exist, worker count provides a conservative
    # three-tile warm-up. Afterwards observed completions raise that ceiling,
    # while travel and outstanding service work consume capacity.
    warmup = workers * 3
    observed = workers + completed * 2 - distance // max(1, workers)
    limit = max(workers, min(warmup + completed, max(warmup, observed) - backlog // 2))
    PRODUCTIVE_ACTION_CAPACITY_FIRES += 1
    return {"acreage_limit": limit, "completed_service": completed,
            "travel_distance": distance, "backlog": backlog,
            "observed_acreage": int(current.get("acreage", 0))}


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


def _task_priority(tile, day, crop_specs=None, fertilizer_available=0):
    if (CARE_LIVESTOCK_COMPONENT and isinstance(tile, dict)
            and tile.get("kind") == "ANIMAL"
            and tile.get("animal") in {"COW", "SHEEP"}):
        if tile.get("care_required", tile.get("needs_care", False)):
            return -2
        if tile.get("feed_required", tile.get("needs_feed", False)):
            return -1
    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop = tile.get("crop", "WHEAT")
        maturity = int((crop_specs or {}).get(crop, {}).get("maturity_days", 2))
        if int(tile.get("yield_units", 0)) > 0 or day - int(tile.get("planted_day", day)) >= maturity:
            return 0
        if (FERTILIZER_COVERAGE and fertilizer_available > 0 and crop == "STRAWBERRY" and
                int(tile.get("fertilized_until_day", -1)) < day):
            return 1
        if not tile.get("watered_today", False):
            return 2
        return None
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return 3
    if tile is None:
        return 4
    return None


def _action_at(tile, day, available_seeds, crop, crop_specs, fertilizer_available=0):
    global FERTILIZER_COVERAGE_FIRES
    priority = _task_priority(tile, day, crop_specs, fertilizer_available)
    if priority == -2:
        return ["CARE"], available_seeds, fertilizer_available
    if priority == -1:
        return ["FEED"], available_seeds, fertilizer_available
    if priority == 0:
        return ["HARVEST"], available_seeds, fertilizer_available
    if priority == 1:
        FERTILIZER_COVERAGE_FIRES += 1
        return ["FERTILIZE"], available_seeds, fertilizer_available - 1
    if priority == 2:
        return ["WATER"], available_seeds, fertilizer_available
    if priority == 3:
        return ["DIG"], available_seeds, fertilizer_available
    if priority == 4 and available_seeds > 0:
        return ["PLANT", crop], available_seeds - 1, fertilizer_available
    return ["PASS"], available_seeds, fertilizer_available


def _plan_workers(me, day, seeds, crop, crop_specs, hour=0, turns_per_day=12,
                  fertilizer_by_worker=(), layout_plan=None):
    global PUBLIC_SCHEDULER_FIRES, MULTI_STOP_TASK_BUNDLE_FIRES
    global CAPACITY_DISPATCHER_FIRES
    tiles = me["tiles"]
    workers = [me["farmer"]] + list(me.get("hands", []))
    fertilizer_by_worker = tuple(max(0, int(value)) for value in fertilizer_by_worker)
    if len(fertilizer_by_worker) < len(workers):
        fertilizer_by_worker += (0,) * (len(workers) - len(fertilizer_by_worker))
    fertilizer_remaining = list(fertilizer_by_worker)
    standing_actions = {}
    standing_positions = set()
    if PUBLIC_SCHEDULER_COMPONENT:
        PUBLIC_SCHEDULER_FIRES += 1
        # Public lonespear v13 insight: consume zero-travel work before global
        # matching so a priority handicap cannot pull a worker off its tile.
        for worker_index, (x, y) in enumerate(workers):
            priority = _task_priority(tiles[y][x], day, crop_specs, fertilizer_remaining[worker_index])
            if priority is None or (x, y) in standing_positions:
                continue
            action, seeds, fertilizer_remaining[worker_index] = _action_at(
                tiles[y][x], day, seeds, crop, crop_specs, fertilizer_remaining[worker_index])
            standing_actions[worker_index] = action
            standing_positions.add((x, y))
    candidates = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            # The capacity controller observes task demand, not private stock.
            # Resource feasibility remains an execution constraint below.
            visible_fertilizer = 1 if CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER else sum(fertilizer_remaining)
            priority = _task_priority(tile, day, crop_specs, visible_fertilizer)
            if priority is not None and (x, y) not in standing_positions:
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

    # SOT-2852: rebuild the dispatcher budget from the current public state on
    # every turn. Standing work is already fixed above. Remaining workforce is
    # split by observed task-tier demand, with an explicit movement allowance;
    # no assignment or route is carried across turns.
    tier_budgets = {}
    travel_budget = len(workers)
    if CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER:
        CAPACITY_DISPATCHER_FIRES += 1
        available = max(0, len(workers) - len(standing_actions))
        demand = {}
        for priority, _, _, _ in candidates:
            demand[priority] = demand.get(priority, 0) + 1
        remaining = available
        for priority in sorted(demand):
            higher_demand = sum(demand[p] for p in demand if p > priority)
            reserve = 1 if higher_demand and remaining > 1 else 0
            tier_budgets[priority] = min(demand[priority], max(0, remaining - reserve))
            remaining -= tier_budgets[priority]
        # Spare workforce goes to the most urgent unfilled tiers.
        for priority in sorted(demand):
            extra = min(remaining, demand[priority] - tier_budgets[priority])
            tier_budgets[priority] += extra
            remaining -= extra
        turns_left = max(1, turns_per_day - hour)
        immediate_capacity = max(1, available * min(3, turns_left))
        travel_budget = max(available, immediate_capacity - sum(demand.values()))
        CAPACITY_DISPATCHER_TELEMETRY["last_tier_budgets"] = dict(tier_budgets)
        CAPACITY_DISPATCHER_TELEMETRY["last_travel_budget"] = travel_budget

    def bundled_tail_cost(task_index):
        """Bounded two-stop VRP proxy using only the current public task set."""
        if not MULTI_STOP_TASK_BUNDLING or len(candidates) < 2:
            return 0
        priority, _, ty, tx = candidates[task_index]
        compatible = [
            abs(nx - tx) + abs(ny - ty)
            for index, (next_priority, _, ny, nx) in enumerate(candidates)
            if index != task_index and next_priority <= priority + 1
        ]
        return min(compatible, default=0)

    @lru_cache(maxsize=None)
    def assign(worker_index, used_mask, occupied_next):
        if worker_index == len(workers):
            return (0, 0, 0), ()
        if worker_index in standing_actions:
            future_cost, future_choices = assign(worker_index + 1, used_mask, occupied_next)
            return future_cost, (-2,) + future_choices
        px, py = workers[worker_index]
        best = None
        occupied = set(occupied_next)
        for task_index, (priority, deadline, ty, tx) in enumerate(candidates):
            if used_mask & (1 << task_index):
                continue
            if priority == 1 and fertilizer_by_worker[worker_index] <= 0:
                continue
            distance = abs(tx - px) + abs(ty - py)
            if CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER and distance > travel_budget:
                continue
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
            density_cost = 0
            if CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER:
                # Spending scarce action capacity on travel has an explicit
                # opportunity cost. Tier demand determines the workforce cap.
                density_cost = distance * (20 + 5 * sum(demand.values()))
                assigned_same_tier = sum(
                    candidates[index][0] == priority
                    for index in range(len(candidates)) if used_mask & (1 << index)
                )
                if assigned_same_tier >= tier_budgets.get(priority, 0):
                    continue
            shed_distance = abs(tx - layout_plan["shed"][0]) + abs(ty - layout_plan["shed"][1]) if layout_plan else 0
            layout_cost = shed_distance * 3 if layout_plan and priority == 4 else 0
            cost = (
                future_cost[0] + conflict,
                future_cost[1] + overdue,
                future_cost[2] + priority * 100 + distance * (4 - min(priority, 3))
                + bundled_tail_cost(task_index) + density_cost + layout_cost,
            )
            proposal = cost, (task_index,) + future_choices
            if best is None or proposal < best:
                best = proposal
        if best is None:
            future_cost, future_choices = assign(worker_index + 1, used_mask, occupied_next)
            return future_cost, (-1,) + future_choices
        return best

    choices = assign(0, 0, ())[1] if candidates or standing_actions else (-1,) * len(workers)
    if MULTI_STOP_TASK_BUNDLING and len(candidates) >= 2 and any(choice >= 0 for choice in choices):
        MULTI_STOP_TASK_BUNDLE_FIRES += 1
    actions = []
    for position, choice in zip(workers, choices):
        worker_index = len(actions)
        if choice == -2:
            actions.append(standing_actions[worker_index])
            continue
        if choice < 0:
            actions.append(["PASS"])
            continue
        px, py = position
        _, _, ty, tx = candidates[choice]
        if [px, py] == [tx, ty]:
            action, seeds, fertilizer_remaining[worker_index] = _action_at(
                tiles[ty][tx], day, seeds, crop, crop_specs, fertilizer_remaining[worker_index])
        else:
            action = _move(position, (tx, ty))
        actions.append(action)
    if CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER:
        CAPACITY_DISPATCHER_TELEMETRY["turns"] += 1
        CAPACITY_DISPATCHER_TELEMETRY["standing"] += len(standing_actions)
        CAPACITY_DISPATCHER_TELEMETRY["productive_assignments"] += len(standing_actions)
        for position, choice, action in zip(workers, choices, actions):
            if choice < 0:
                continue
            priority = candidates[choice][0]
            key = str(priority)
            tiers = CAPACITY_DISPATCHER_TELEMETRY["tier_assignments"]
            tiers[key] = tiers.get(key, 0) + 1
            CAPACITY_DISPATCHER_TELEMETRY["productive_assignments"] += 1
            if action[0] in {"NORTH", "SOUTH", "EAST", "WEST"}:
                CAPACITY_DISPATCHER_TELEMETRY["travel_steps"] += 1
    # A later worker may approach a different task through the same intermediate
    # cell. Resolve that one-turn collision deterministically after assignment.
    reserved_moves = set()
    for index, (position, action) in enumerate(zip(workers, actions)):
        if action[0] not in {"NORTH", "SOUTH", "EAST", "WEST"}:
            continue
        destination = _next_position(position, action)
        if destination in reserved_moves:
            actions[index] = ["PASS"]
            if CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER:
                CAPACITY_DISPATCHER_TELEMETRY["budget_repairs"] += 1
        else:
            reserved_moves.add(destination)
    return actions


def _layout_aware_production_plan(obs, requested_seeds):
    """Bound planting demand by executable service capacity and shed logistics.

    The component consumes only the current public board, worker positions and
    clock.  It is an upstream demand/layout architecture: its output caps the
    planting demand passed to the dispatcher and supplies a shed-distance cost
    for placement, rather than changing dispatcher priority weights.
    """
    global LAYOUT_AWARE_PRODUCTION_FIRES
    if not LAYOUT_AWARE_PRODUCTION_ARCHITECTURE:
        return None
    me = obs["farms"][int(obs["player"])]
    tiles = me.get("tiles", [])
    workers = [me.get("farmer", [0, 0]), *me.get("hands", [])]
    turns_per_day = max(1, int(obs.get("turns_per_day", 24)))
    total_steps = max(0, int(obs.get("total_days", 30)) * turns_per_day)
    step = int(obs.get("step", int(obs.get("day", 0)) * turns_per_day + int(obs.get("hour", 0))))
    remaining = max(0, total_steps - step)
    shed = tuple(int(value) for value in me.get("shed_position", [0, 0])[:2])
    service_demand = 0
    planted = 0
    empty_distances = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                planted += 1
                if (int(tile.get("yield_units", 0)) > 0 or not tile.get("watered_today", False)
                        or int(tile.get("fertilized_until_day", int(obs.get("day", 0)))) < int(obs.get("day", 0))):
                    service_demand += 1
            elif tile is None:
                empty_distances.append(abs(x - shed[0]) + abs(y - shed[1]))
    # Each new crop needs planting plus at least water/harvest service.  Reserve
    # current due work first and admit only demand executable before deadline.
    action_capacity = max(0, len(workers) * remaining - service_demand)
    completion_cap = min(len(empty_distances), action_capacity // 3)
    demand = min(max(0, int(requested_seeds)), completion_cap)
    plan = {
        "shed": shed, "requested": max(0, int(requested_seeds)), "admitted": demand,
        "existing_crops": planted, "service_demand": service_demand,
        "remaining_actions": action_capacity,
        "nearest_open_distance": min(empty_distances, default=None),
    }
    LAYOUT_AWARE_PRODUCTION_FIRES += 1
    LAYOUT_AWARE_PRODUCTION_TELEMETRY["demand_caps"] += int(demand < max(0, int(requested_seeds)))
    LAYOUT_AWARE_PRODUCTION_TELEMETRY["shed_weighted_assignments"] += int(bool(demand and empty_distances))
    LAYOUT_AWARE_PRODUCTION_TELEMETRY["last_plan"] = dict(plan)
    return plan


def _layout_aware_pasture_action(obs, actions, plan):
    """Place one publicly-demanded pasture at the nearest shed-side tile."""
    if plan is None or not obs.get("animals"):
        return actions
    me = obs["farms"][int(obs["player"])]
    tiles = me.get("tiles", [])
    if any(isinstance(tile, dict) and tile.get("kind") == "PASTURE"
           for row in tiles for tile in row):
        return actions
    shed = plan["shed"]
    empty = sorted((abs(x - shed[0]) + abs(y - shed[1]), y, x)
                   for y, row in enumerate(tiles) for x, tile in enumerate(row)
                   if tile is None)
    if not empty:
        return actions
    _, ty, tx = empty[0]
    workers = [me.get("farmer", [0, 0]), *me.get("hands", [])]
    choice = min((abs(int(pos[0]) - tx) + abs(int(pos[1]) - ty), index)
                 for index, pos in enumerate(workers))[1]
    amended = list(actions)
    position = tuple(workers[choice])
    amended[choice] = (["BUILD_PASTURE"] if position == (tx, ty)
                       else _move(position, (tx, ty)))
    if amended[choice][0] == "BUILD_PASTURE":
        LAYOUT_AWARE_PRODUCTION_TELEMETRY["pasture_placements"] += 1
    return amended


def _projected_shed_inventory(private, actions):
    """Project products dropped before same-turn market orders execute."""
    projected = {str(item): max(0, int(amount))
                 for item, amount in private.get("shed", {}).items()}
    inventories = list(private.get("inventories", []))
    for index, action in enumerate(actions):
        if action and action[0] == "DROP" and index < len(inventories):
            carried = inventories[index]
            if isinstance(carried, dict):
                for item, amount in carried.items():
                    projected[str(item)] = projected.get(str(item), 0) + max(0, int(amount))
    return projected


def _protect_shed_capacity(obs, actions, crop_specs):
    """Bound nightly loss using only own inventory, public capacity, and clock."""
    global SHED_OVERFLOW_FIRES
    if not SHED_OVERFLOW_PROTECTION:
        return actions, []
    private = obs.get("private", {})
    shed = private.get("shed", {})
    inventories = list(private.get("inventories", []))
    capacity = max(0, int(obs.get("shed_capacity", 100)))
    shed_total = sum(max(0, int(amount)) for amount in shed.values())
    carried = [sum(max(0, int(amount)) for amount in inventory.values())
               if isinstance(inventory, dict) else 0 for inventory in inventories]
    carried_total = sum(carried)
    if carried_total <= 0:
        return actions, []

    protected_actions = list(actions)
    room = max(0, capacity - shed_total)
    for index, amount in enumerate(carried):
        if (amount > 0 and amount <= room and index < len(protected_actions)
                and protected_actions[index][0] == "PASS"):
            protected_actions[index] = ["DROP"]
            room -= amount
            SHED_OVERFLOW_FIRES += 1

    hour = max(0, int(obs.get("hour", 0)))
    turns_per_day = max(1, int(obs.get("turns_per_day", 24)))
    overflow = max(0, shed_total + carried_total - capacity)
    if hour < turns_per_day - 1 or overflow <= 0:
        return protected_actions, []
    orders = []
    remaining = overflow
    prices = obs.get("market", {}).get("prices", {})
    for item in sorted(shed, key=lambda value: (int(prices.get(value, 0)), value)):
        amount = min(max(0, int(shed.get(item, 0))), remaining)
        if amount > 0 and (item in crop_specs or int(prices.get(item, 0)) > 0):
            orders.append(["SELL", item, amount])
            remaining -= amount
            SHED_OVERFLOW_FIRES += 1
        if remaining <= 0:
            break
    return protected_actions, orders


def _sale_priority(obs, crop):
    """Order fragile sales before publicly exposed, glut-sensitive products."""
    player = int(obs.get("player", 0))
    exposure = 0
    for index, farm in enumerate(obs.get("farms", [])):
        if index == player:
            continue
        exposure += sum(
            max(0, int(tile.get("yield_units", 0)))
            for row in farm.get("tiles", []) for tile in row
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop
        )
    market = obs.get("market", {})
    inventory = max(0, int(market.get("inventory", {}).get(crop, 0)))
    anchor = max(1, int(market.get("inventory_anchor", {}).get(crop, max(1, inventory))))
    glut = inventory / anchor
    return (-exposure, -glut, crop)


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


def _staggered_strawberry_seed_budget(obs, spec, available_seeds, fertilizer_available):
    """Bound one day's strawberry cohort using only public lifecycle state.

    Strawberry is an ongoing crop in the competition runtime.  A full block
    planted on one day therefore reaches ``max_lifespan_step`` together.  Keep
    at most one maturity-window slice in today's cohort, while allowing extra
    replacements for plants that are already inside their last maturity
    window.  Labor and fertilizer stock bound the replacement acreage so the
    policy cannot create work that the remaining horizon cannot service.
    """
    global STAGGERED_STRAWBERRY_RENEWAL_FIRES
    if not STAGGERED_STRAWBERRY_RENEWAL:
        return max(0, int(available_seeds))
    day = max(0, int(obs.get("day", 0)))
    total_days = max(day + 1, int(obs.get("total_days", 30)))
    maturity = max(1, int(spec.get("first_yield_day", spec.get("maturity_days", 3))))
    if day + maturity >= total_days:
        STAGGERED_STRAWBERRY_RENEWAL_FIRES += 1
        return 0
    step = int(obs.get("step", day * int(obs.get("turns_per_day", 24))))
    me = obs["farms"][int(obs["player"])]
    plants = [tile for row in me.get("tiles", []) for tile in row
              if isinstance(tile, dict) and tile.get("kind") == "PLANT"
              and tile.get("crop") == "STRAWBERRY"]
    planted_today = sum(int(tile.get("planted_day", -1)) == day for tile in plants)
    expiring = sum(
        step < int(tile.get("max_lifespan_step", step + maturity + 1))
        <= step + maturity * int(obs.get("turns_per_day", 24))
        for tile in plants
    )
    workers = 1 + len(me.get("hands", []))
    # A maturity-length rotation avoids a one-wave cohort.  Fertilizer is a
    # hard coverage cap when present; without public stock, labor remains the
    # conservative capacity bound.
    service_capacity = workers
    if fertilizer_available > 0:
        service_capacity = min(service_capacity, max(1, fertilizer_available // maturity))
    cohort_target = max(1, ceil(max(1, len(plants) + expiring) / maturity))
    budget = max(0, min(service_capacity, cohort_target + expiring) - planted_today)
    budget = min(max(0, int(available_seeds)), budget)
    STAGGERED_STRAWBERRY_RENEWAL_FIRES += 1
    return budget


def _fertilizer_constrained_production_plan(obs, crop, spec, requested_seeds,
                                            fertilizer_available):
    """Admit only acreage whose recurring crop cycle is budget-feasible.

    This is deliberately independent from the rejected fixed-layout and generic
    capacity controllers.  It works backwards from the remaining public clock:
    every admitted ongoing crop must have worker actions for plant, fertilize,
    water and harvest, enough observed fertilizer, cash runway after seed/hire
    cost, and shed room or a terminal liquidation slot.  The plan contains no
    fixed acreage, quadrant, hand count, route, replay identity, or future data.
    """
    global FERTILIZER_CONSTRAINED_PRODUCTION_FIRES
    if not FERTILIZER_CONSTRAINED_PRODUCTION:
        return None
    player = int(obs.get("player", 0))
    me = obs["farms"][player]
    day = max(0, int(obs.get("day", 0)))
    total_days = max(day + 1, int(obs.get("total_days", 30)))
    turns_per_day = max(1, int(obs.get("turns_per_day", 24)))
    hour = max(0, int(obs.get("hour", 0)))
    remaining_turns = max(0, (total_days - day - 1) * turns_per_day
                          + max(0, turns_per_day - hour))
    workers = 1 + len(me.get("hands", ()))
    tiles = me.get("tiles", ())
    existing = [tile for row in tiles for tile in row
                if isinstance(tile, dict) and tile.get("kind") == "PLANT"]
    existing_due = sum(
        int(int(tile.get("yield_units", 0)) > 0)
        + int(not tile.get("watered_today", False))
        + int(int(tile.get("fertilized_until_day", day)) < day)
        for tile in existing
    )
    # Reserve one quarter of capacity for travel/collision recovery.  A new
    # ongoing crop then consumes plant + fertilize + water + harvest for every
    # harvest cycle that can still complete.
    usable_actions = max(0, (workers * remaining_turns * 3) // 4 - existing_due)
    cycles = max(1, _remaining_harvests(spec, day, total_days))
    actions_per_acre = 1 + 3 * cycles
    action_cap = usable_actions // actions_per_acre
    fertilizer_cap = max(0, int(fertilizer_available)) // cycles

    money = max(0, int(me.get("money", 0)))
    seed_price = max(0, int(spec.get("seed_price", 0)))
    hands = len(me.get("hands", ()))
    hire_cost = _hire_cost(int(me.get("hires_today", hands))) if hands < MIN_HAND_TARGET else 0
    runway = MIN_CASH_RESERVE + hire_cost
    cash_cap = max(0, money - runway) // max(1, seed_price)

    private = obs.get("private", {})
    shed = private.get("shed", {})
    used_shed = sum(max(0, int(value)) for value in shed.values()) if isinstance(shed, dict) else 0
    shed_capacity = max(0, int(obs.get("shed_capacity", me.get("shed_capacity", 0))))
    liquidation_slots = max(0, MAX_MARKET_ORDERS - 1)
    yield_per_acre = max(1, int(spec.get("expected_yield", 1)))
    if shed_capacity > 0:
        shed_headroom = max(0, shed_capacity - used_shed)
        # One terminal SELL can drain this crop; until then at least one harvest
        # wave must fit in the shed.
        shed_cap = shed_headroom // yield_per_acre if liquidation_slots else 0
    else:
        shed_cap = max(0, int(requested_seeds))

    requested = max(0, int(requested_seeds))
    admitted = min(requested, action_cap, cash_cap, shed_cap)
    if crop == "STRAWBERRY":
        admitted = min(admitted, fertilizer_cap)
    plan = {
        "crop": crop, "requested": requested, "admitted": admitted,
        "workers": workers, "remaining_turns": remaining_turns,
        "cycles": cycles, "actions_per_acre": actions_per_acre,
        "usable_actions": usable_actions, "action_cap": action_cap,
        "fertilizer_available": max(0, int(fertilizer_available)),
        "fertilizer_cap": fertilizer_cap, "cash": money, "cash_runway": runway,
        "hire_cost": hire_cost, "cash_cap": cash_cap, "shed_used": used_shed,
        "shed_capacity": shed_capacity, "shed_cap": shed_cap,
        "terminal_liquidation_slots": liquidation_slots,
    }
    FERTILIZER_CONSTRAINED_PRODUCTION_FIRES += 1
    telemetry = FERTILIZER_CONSTRAINED_PRODUCTION_TELEMETRY
    telemetry["plans"] += 1
    telemetry["demand_caps"] += int(admitted < requested)
    telemetry["supply_caps"] += int(crop == "STRAWBERRY" and fertilizer_cap < requested)
    telemetry["action_caps"] += int(action_cap < requested)
    telemetry["cash_caps"] += int(cash_cap < requested)
    telemetry["shed_caps"] += int(shed_cap < requested)
    telemetry["last_plan"] = plan
    return plan


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


def _compact_replay_production(obs, harvests_left, record=False):
    """Return the screen-distilled land/labor targets from public state.

    The policy is deliberately a tiny threshold table.  It claims no task
    coordinates and consumes neither replay identity nor private inventory.
    Land count conditions labor, so this is not the rejected static headcount
    axis: additional workers are requested only after the matching production
    capacity milestone has actually become public.
    """
    if not COMPACT_REPLAY_POLICY or harvests_left <= 0:
        return {"land": [], "hand_target": None, "branch": "disabled"}
    me = obs["farms"][int(obs["player"])]
    day = max(0, int(obs.get("day", 0)))
    unlocked = len(me.get("unlocked_quadrants", ()))
    desired_land = 1
    milestone_hour = None
    for milestone_day, hour, target in COMPACT_REPLAY_POLICY_CONSTANTS["land_milestones"]:
        if day >= milestone_day:
            desired_land = target
            if day == milestone_day:
                milestone_hour = hour
    land = ([['BUY_LAND']] if unlocked < desired_land
            and milestone_hour == int(obs.get("hour", 0)) else [])
    if land and record:
        COMPACT_REPLAY_POLICY_FIRES["land"] += 1
    hand_targets = COMPACT_REPLAY_POLICY_CONSTANTS["hands_per_unlocked_quadrant"]
    target_index = max(0, min(len(hand_targets) - 1, unlocked - 1))
    hand_target = hand_targets[target_index]
    if len(me.get("hands", ())) < hand_target and record:
        COMPACT_REPLAY_POLICY_FIRES["labor"] += 1
    return {"land": land, "hand_target": hand_target,
            "branch": f"land_{unlocked}_target_{desired_land}"}


def _runway_expansion_plan(obs, crop_spec, crop, harvests_left):
    """Permit one public-state capacity step after operating reserves are funded."""
    global CASH_RUNWAY_ACREAGE_FIRES
    if not CASH_RUNWAY_ACREAGE_EXPANSION or harvests_left <= 0:
        return {"reserve": MIN_CASH_RESERVE, "land": [], "extra_seeds": 0,
                "serviceable_hands": None}
    me = obs["farms"][int(obs["player"])]
    private = obs.get("private", {})
    money = max(0, int(me.get("money", 0)))
    hands = list(me.get("hands", []))
    workers = 1 + len(hands)
    seed_price = max(1, int(crop_spec.get("seed_price", 0)))
    seed_reserve = workers * SEED_RESERVE_PER_WORKER * seed_price
    herd = sum(max(0, int(value)) for value in private.get("animals", {}).values())
    feed_price = max(0, int(obs.get("market", {}).get("prices", {}).get("FEED", 0)))
    feed_reserve = herd * max(1, int(obs.get("feed_reserve_days", 2))) * feed_price
    care_reserve = max(0, int(me.get("daily_operating_cost", 0))) * min(3, harvests_left)
    reserve = max(MIN_CASH_RESERVE, seed_reserve + feed_reserve + care_reserve)
    usable = sum(tile != "LOCKED" for row in me.get("tiles", []) for tile in row)
    serviceable_hands = max(0, min(MAX_HAND_TARGET, ceil(usable / 6) - 1))
    orders = []
    capabilities = set(obs.get("capabilities", ()))
    unlocked = list(me.get("unlocked_quadrants", ["NW"]))
    land_costs = obs.get("land_costs", ())
    if isinstance(land_costs, (list, tuple)) and len(land_costs) > len(unlocked) - 1:
        land_cost = max(0, int(land_costs[len(unlocked) - 1]))
    else:
        land_cost = 1000 * (2 ** max(0, len(unlocked) - 1))
    remaining_days = max(0, int(obs.get("total_days", 30)) - int(obs.get("day", 0)))
    maturity = max(1, int(crop_spec.get("maturity_days", 2)))
    # One order per observation makes expansion incremental and auditable.
    if ("BUY_LAND" in capabilities and len(unlocked) < 4
            and remaining_days > maturity * 2 and workers >= serviceable_hands
            and money - land_cost >= reserve):
        orders.append(["BUY_LAND"])
        money -= land_cost
        CASH_RUNWAY_ACREAGE_FIRES += 1
    extra_seeds = int(money - seed_price >= reserve and usable > workers * SEED_RESERVE_PER_WORKER)
    if extra_seeds:
        CASH_RUNWAY_ACREAGE_FIRES += 1
    return {"reserve": reserve, "land": orders, "extra_seeds": extra_seeds,
            "serviceable_hands": serviceable_hands}


def _care_livestock_orders(obs, route=None):
    """Buy bounded cow/sheep capacity only when remaining CARE cycles repay it."""
    global CARE_LIVESTOCK_FIRES
    if not CARE_LIVESTOCK_COMPONENT:
        return []
    capabilities = set(obs.get("capabilities", ()))
    if "BUY_ANIMAL" not in capabilities:
        return []
    day = max(0, int(obs.get("day", 0)))
    total_days = max(day + 1, int(obs.get("total_days", 30)))
    remaining_days = total_days - day
    me = obs["farms"][int(obs["player"])]
    money = max(0, int(me.get("money", 0)))
    private = obs.get("private", {})
    herd = private.get("animals", {})
    shed = private.get("shed", {})
    prices = obs.get("market", {}).get("prices", {})
    animal_specs = obs.get("animals", {})
    orders = []
    committed = 0
    candidates = []
    targets = {"COW": 2, "SHEEP": 2}
    if route:
        raw_total = max(1, route["cow_target"] + route["sheep_target"])
        # Preserve the champion's bounded herd constraint while following the
        # selected route's public cow/sheep ratio.
        targets = {
            "COW": max(1, min(2, round(4 * route["cow_target"] / raw_total))),
            "SHEEP": max(1, min(2, round(4 * route["sheep_target"] / raw_total))),
        }
    for animal, product in (("COW", "MILK"), ("SHEEP", "WOOL")):
        spec = animal_specs.get(animal, {})
        capital = max(0, int(spec.get("price", 0)))
        interval = max(1, int(spec.get("care_interval_days", 2)))
        cycles = remaining_days // interval
        units = max(1, int(spec.get("product_per_care", 1)))
        feed_per_cycle = max(0, int(spec.get("feed_per_care", 1)))
        feed_price = max(0, int(prices.get("FEED", spec.get("feed_price", 0))))
        product_price = max(0, int(prices.get(product, spec.get("product_price", 0))))
        net = cycles * (units * product_price - feed_per_cycle * feed_price) - capital
        deficit = max(0, targets[animal] - max(0, int(herd.get(animal, 0))))
        candidates.append((deficit > 0, net, animal, capital, cycles))
    for wanted, net, animal, capital, cycles in sorted(candidates, reverse=True):
        owned = max(0, int(herd.get(animal, 0)))
        runway = max(MIN_CASH_RESERVE * 2, int(me.get("daily_operating_cost", 0)) * 3)
        if wanted and owned < targets[animal] and cycles >= 2 and net > 0 and money - committed - capital >= runway:
            orders.append(["BUY_ANIMAL", animal, 1])
            committed += capital
            CARE_LIVESTOCK_FIRES += 1
            break
    herd_size = sum(max(0, int(herd.get(animal, 0))) for animal in ("COW", "SHEEP"))
    feed_needed = max(0, herd_size * 2 - int(shed.get("FEED", 0)))
    feed_price = max(0, int(prices.get("FEED", 0)))
    affordable_feed = max(0, (money - committed - MIN_CASH_RESERVE) // max(1, feed_price))
    if feed_needed and feed_price and "BUY_PRODUCT" in capabilities:
        orders.append(["BUY_PRODUCT", "FEED", min(feed_needed, affordable_feed)])
        CARE_LIVESTOCK_FIRES += 1
    return [order for order in orders if len(order) < 3 or order[2] > 0]


def _feed_economic_order(obs):
    """Fund a bounded wheat runway for the current herd from current state.

    The source winner used a coherent schedule with large feed-wheat buys.  We
    retain only its economic decision: buy enough wheat for the observable
    herd's near-term feed cycles when cash runway and public shop demand make
    those cycles supportable.  No schedule position or replay identity enters
    this calculation, and the independent flag permits a clean ablation.
    """
    global FEED_ECONOMIC_FIRES
    if not FEED_ECONOMIC_DECISION or "BUY_PRODUCT" not in set(obs.get("capabilities", ())):
        return []
    player = int(obs.get("player", 0))
    me = obs.get("farms", [{}])[player]
    private = obs.get("private", {})
    herd = sum(max(0, int(count)) for count in private.get("animals", {}).values())
    if not herd:
        return []
    day = max(0, int(obs.get("day", 0)))
    remaining_days = max(0, int(obs.get("total_days", 30)) - day)
    if not remaining_days:
        return []
    prices = obs.get("market", {}).get("prices", {})
    wheat_price = max(0, int(prices.get("WHEAT", 0)))
    if not wheat_price:
        return []
    shops = obs.get("town", {}).get("unlocked_shops", ()) or ()
    livestock_demand = sum(any(token in str(shop) for token in ("MILK", "WOOL", "YARN", "CHEESE"))
                           for shop in shops)
    # Cover at most four current feed cycles.  Public downstream demand adds
    # one cycle, but never changes the herd-bounded maximum.
    cycles = min(4, remaining_days, 2 + int(bool(livestock_demand)))
    target = herd * cycles
    shed_wheat = max(0, int(private.get("shed", {}).get("WHEAT", 0)))
    carried_wheat = sum(max(0, int(inventory.get("WHEAT", 0)))
                        for inventory in private.get("inventories", ())
                        if isinstance(inventory, dict))
    needed = max(0, target - shed_wheat - carried_wheat)
    money = max(0, int(me.get("money", 0)))
    operating = max(0, int(me.get("daily_operating_cost", 0)))
    reserve = max(MIN_CASH_RESERVE * 2, operating * min(3, remaining_days))
    affordable = max(0, (money - reserve) // wheat_price)
    quantity = min(20, needed, affordable)
    if not quantity:
        return []
    FEED_ECONOMIC_FIRES += 1
    return [["BUY_PRODUCT", "WHEAT", quantity]]


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


def _v21_late_capital_orders(obs, market):
    """Latch a public bank lead once, then suppress only new capital orders."""
    global V21_LATE_CAPITAL_LATCH_FIRES, V21_LATE_CAPITAL_SUPPRESSED_ORDERS
    if not V21_ONE_TIME_LATE_CAPITAL_LATCH:
        return market
    step = max(0, int(obs.get("step", 0)))
    player = int(obs.get("player", 0))
    farms = obs.get("farms", ())
    if player not in (0, 1) or len(farms) != 2:
        return market
    previous = V21_LATE_CAPITAL_LATCH_STATE.get(player)
    if step == 0 or (previous is not None and step < previous["decision_step"]):
        V21_LATE_CAPITAL_LATCH_STATE.pop(player, None)
        previous = None
    if previous is None and step >= V21_LATE_CAPITAL_START_STEP:
        own_bank = max(0, int(farms[player].get("money", 0)))
        rival_bank = max(0, int(farms[1 - player].get("money", 0)))
        previous = {
            "seat": player,
            "decision_step": step,
            "own_bank": own_bank,
            "rival_bank": rival_bank,
            "bank_lead": own_bank - rival_bank,
            "latched": own_bank - rival_bank >= V21_LATE_CAPITAL_LEAD_THRESHOLD,
        }
        V21_LATE_CAPITAL_LATCH_STATE[player] = previous
        V21_LATE_CAPITAL_LATCH_DECISIONS.append(dict(previous))
    if previous is None or not previous["latched"]:
        return market
    filtered = [order for order in market
                if not (isinstance(order, list) and order
                        and order[0] in V21_CAPITAL_ORDER_TYPES)]
    removed = len(market) - len(filtered)
    if removed:
        V21_LATE_CAPITAL_LATCH_FIRES += 1
        V21_LATE_CAPITAL_SUPPRESSED_ORDERS += removed
    return filtered


def _moon_v56_tomato_scarcity_action(obs, action):
    """Port Moon V56's tomato fork as a bounded, independently gated patch.

    Exactly three strawberry cohort slots are redirected.  A displaced seed
    order is relayed for at most eight public-clock slots, and the state is
    isolated per seat.  The trigger uses only the first three public shops;
    later tracking uses the public clock, own visible tiles/actions, and own
    inventory needed to execute the selected actions.
    """
    if not MOON_V56_TOMATO_SCARCITY_FORK:
        return action
    seat = int(obs.get("player", 0))
    if seat not in _MOON_V56_TOMATO_STATE:
        return action
    step = max(0, int(obs.get("step", 0)))
    state = _MOON_V56_TOMATO_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {"last_step": step, "active": False, "seed_debt": 0,
                 "plants": 0, "harvests": 0}
        _MOON_V56_TOMATO_STATE[seat] = state
    state["last_step"] = step
    if step == MOON_V56_TRIGGER_STEP and not state["active"]:
        shops = list(obs.get("town", {}).get("unlocked_shops", ()) or ())[:3]
        state["active"] = sum(
            shop in {"FARMERS_MARKET", "PIZZA_SHOP"} for shop in shops) >= 2
        if state["active"]:
            MOON_V56_TOMATO_SCARCITY_FIRES["trigger"] += 1
    if not state["active"]:
        return action

    amended = {
        "farmer": list(action.get("farmer", ["PASS"])),
        "hands": [list(order) for order in action.get("hands", ())],
        "market": [list(order) for order in action.get("market", ())],
    }
    market = amended["market"]
    if step == MOON_V56_SEED_STEP and not state["seed_debt"]:
        strawberry = next((order for order in market
                           if len(order) >= 3 and order[:2] == ["BUY_SEED", "STRAWBERRY"]
                           and int(order[2]) >= MOON_V56_TOMATO_TARGET), None)
        if strawberry is not None:
            strawberry[2] = int(strawberry[2]) - MOON_V56_TOMATO_TARGET
            state["seed_debt"] = MOON_V56_TOMATO_TARGET
    if (state["seed_debt"] and MOON_V56_SEED_STEP < step <=
            MOON_V56_SEED_STEP + MOON_V56_RELAY_LIMIT and len(market) < MAX_MARKET_ORDERS):
        market.append(["BUY_SEED", "TOMATO", state["seed_debt"]])
        state["seed_debt"] = 0
        MOON_V56_TOMATO_SCARCITY_FIRES["seed_relay"] += 1

    orders = [amended["farmer"], *amended["hands"]]
    if MOON_V56_PLANT_WINDOW[0] <= step <= MOON_V56_PLANT_WINDOW[1]:
        remaining = max(0, MOON_V56_TOMATO_TARGET - state["plants"])
        for order in orders:
            if remaining and len(order) >= 2 and order[:2] in (
                    ["PLANT", "STRAWBERRY"], ["PLACE", "STRAWBERRY"]):
                order[1] = "TOMATO"
                remaining -= 1
                state["plants"] += 1
                MOON_V56_TOMATO_SCARCITY_FIRES["plant"] += 1

    farm = obs.get("farms", [{}])[seat]
    tiles = farm.get("tiles", ())
    positions = [farm.get("farmer", (0, 0)), *farm.get("hands", ())]
    for position, order in zip(positions, orders):
        if state["harvests"] >= 12 or not order or order[0] != "HARVEST":
            continue
        x, y = int(position[0]), int(position[1])
        tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else None
        if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "TOMATO":
            state["harvests"] += 1
            MOON_V56_TOMATO_SCARCITY_FIRES["harvest"] += 1

    if step >= MOON_V56_TERMINAL_STEP:
        tomatoes = max(0, int(obs.get("private", {}).get("shed", {}).get("TOMATO", 0)))
        existing = next((order for order in market
                         if len(order) >= 3 and order[:2] == ["SELL", "TOMATO"]), None)
        if tomatoes and existing is not None:
            existing[2] = max(int(existing[2]), tomatoes)
            MOON_V56_TOMATO_SCARCITY_FIRES["terminal_sale"] += 1
        elif tomatoes and len(market) < MAX_MARKET_ORDERS:
            market.append(["SELL", "TOMATO", tomatoes])
            MOON_V56_TOMATO_SCARCITY_FIRES["terminal_sale"] += 1
    return amended


def _policy_action(obs):
    global PROJECTED_MARKET_FIRES, CARE_LIVESTOCK_FIRES, CASH_RUNWAY_ACREAGE_FIRES
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
    public_route = None
    if PUBLIC_SHOP_PREFIX_ROUTE_SELECTOR:
        _, public_route = _public_shop_prefix_route(obs, record=True)
        route_crop = public_route["crop"]
        if route_crop in crop_specs and _remaining_harvests(
                crop_specs[route_crop], day, total_days) > 0:
            crop = route_crop
    mixed_route = None
    if LONG_HORIZON_MIXED_FARM_ROUTE:
        mixed_route = _mixed_farm_route({**obs, "total_days": total_days}, crop_specs, seed_inventory)
        crop = mixed_route["crop"]
    prices = obs.get("market", {}).get("prices", {})
    seeds = int(seed_inventory.get(crop, 0))
    fertilizer_by_worker = [
        max(0, int(inventory.get("FERTILIZER", 0))) if isinstance(inventory, dict) else 0
        for inventory in private.get("inventories", [])
    ]
    planting_seeds = seeds
    if crop == "STRAWBERRY":
        planting_seeds = _staggered_strawberry_seed_budget(
            {**obs, "total_days": total_days}, crop_specs[crop], seeds,
            sum(fertilizer_by_worker))
    fertilizer_plan = _fertilizer_constrained_production_plan(
        {**obs, "total_days": total_days}, crop, crop_specs[crop], planting_seeds,
        sum(fertilizer_by_worker))
    if fertilizer_plan is not None:
        planting_seeds = fertilizer_plan["admitted"]
    capacity = None
    if PRODUCTIVE_ACTION_CAPACITY:
        capacity = _productive_capacity_limit({**obs, "total_days": total_days}, history)
        planting_seeds = min(planting_seeds, max(
            0, capacity["acreage_limit"] - capacity["observed_acreage"]))
    layout_plan = _layout_aware_production_plan(obs, planting_seeds)
    if layout_plan is not None:
        planting_seeds = layout_plan["admitted"]
    actions = _plan_workers(
        me, day, planting_seeds, crop, crop_specs, int(obs.get("hour", 0)),
        int(obs.get("turns_per_day", 12)), fertilizer_by_worker, layout_plan)
    actions = _layout_aware_pasture_action(obs, actions, layout_plan)
    actions = _sequence_planner_actions(obs, actions, crop, crop_specs)
    actions = _sequence_precursor_actions(obs, actions)
    actions, overflow_orders = _protect_shed_capacity(obs, actions, crop_specs)
    stored_inventory = private.get("shed", {})
    if PROJECTED_MARKET_EXECUTION:
        PROJECTED_MARKET_FIRES += 1
        stored_inventory = _projected_shed_inventory(private, actions)
    pressure = _scarcity_pressure(obs, crop) if OPPONENT_AWARE_POLICY else {
        "inventory": 0.0, "labor": 0.0, "field_demand": 0.0, "cash": 0.0, "total": 0.0
    }
    sale_orders = []
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
            sale_orders.append(["SELL", stored_crop, sellable])

    if CARE_LIVESTOCK_COMPONENT:
        for animal, product in (("COW", "MILK"), ("SHEEP", "WOOL")):
            stored = max(0, int(stored_inventory.get(product, 0)))
            price = max(0, int(prices.get(product, 0)))
            spec = obs.get("animals", {}).get(animal, {})
            target = max(0, int(spec.get("product_sell_above", price)))
            if stored and price and (day >= total_days - 1 or price >= target):
                sale_orders.append(["SELL", product, stored])
                CARE_LIVESTOCK_FIRES += 1

    if PROJECTED_MARKET_EXECUTION:
        sale_orders.sort(key=lambda order: _sale_priority(obs, order[1]))
    overflow_sold = {order[1]: order[2] for order in overflow_orders}
    market.extend(overflow_orders)
    market.extend([order[0], order[1], order[2] - overflow_sold.get(order[1], 0)]
                  for order in sale_orders
                  if order[2] > overflow_sold.get(order[1], 0))

    if mixed_route:
        market.extend(mixed_route["market"])

    market.extend(_care_livestock_orders(
        {**obs, "total_days": total_days}, public_route))
    market.extend(_feed_economic_order({**obs, "total_days": total_days}))

    harvests_left = _remaining_harvests(crop_specs[crop], day, total_days)
    compact = _compact_replay_production(
        {**obs, "total_days": total_days}, harvests_left, record=True)
    expansion = _runway_expansion_plan(
        {**obs, "total_days": total_days}, crop_specs[crop], crop, harvests_left)
    if capacity is not None and capacity["observed_acreage"] >= capacity["acreage_limit"]:
        expansion["land"] = []
        expansion["extra_seeds"] = 0
    market.extend(expansion["land"])
    market.extend(compact["land"])
    advance_reserve = 1 if pressure["labor"] + pressure["field_demand"] >= 0.75 else 0
    desired_seeds = (worker_count * SEED_RESERVE_PER_WORKER + advance_reserve
                     + expansion["extra_seeds"] if harvests_left else 0)
    buy_count = max(0, desired_seeds - seeds)
    seed_price = int(crop_specs[crop]["seed_price"])
    affordable = max(0, (money - expansion["reserve"]) // max(1, seed_price))
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
    if compact["hand_target"] is not None:
        hand_target = compact["hand_target"]
    if expansion["serviceable_hands"] is not None:
        hand_target = min(hand_target, expansion["serviceable_hands"])
    if fertilizer_plan is not None:
        # Do not incur another Fibonacci hire unless the admitted acreage can
        # repay it while retaining the explicit cash runway.
        repayable_hands = max(0, ceil(fertilizer_plan["admitted"] / 3))
        hand_target = min(hand_target, repayable_hands)
    if len(hands) < hand_target:
        cost = _hire_cost(hires_today)
        opportunity = expected_crop_margin * harvests_left * (1 + pressure["field_demand"])
        if money - cost >= expansion["reserve"] and opportunity > cost:
            market.append(["HIRE"])
            CASH_RUNWAY_ACREAGE_FIRES += 1

    market = _v21_late_capital_orders(obs, market)
    action = {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[:MAX_MARKET_ORDERS],
    }
    action = _public_step0_wheat_market_lead_action(obs, action)
    return _moon_v56_tomato_scarcity_action(obs, action)


def _public_step0_wheat_market_lead_action(obs, action):
    """Independently reproduce the observed step-0 five-WHEAT market decision.

    This is deliberately a narrow action-family intervention.  It never
    changes worker actions or existing market orders and remains exact-control
    when disabled or outside the one public-state trigger.
    """
    if not PUBLIC_STEP0_WHEAT_MARKET_LEAD:
        return action
    step = int(obs.get("step", int(obs.get("day", 0)) * int(obs.get("turns_per_day", 24))
                              + int(obs.get("hour", 0))))
    player = int(obs.get("player", 0))
    farms = obs.get("farms", ())
    money = int(farms[player].get("money", 0)) if 0 <= player < len(farms) else 0
    price = int(obs.get("market", {}).get("prices", {}).get("WHEAT", 0))
    if (step != 0 or "town" not in obs or "shed_capacity" in obs
            or price <= 0 or money < 5 * price):
        return action
    amended = {"farmer": action["farmer"], "hands": action["hands"],
               "market": list(action.get("market", ()))[:MAX_MARKET_ORDERS - 1]}
    amended["market"].insert(0, ["BUY_PRODUCT", "WHEAT", 5])
    PUBLIC_STEP0_WHEAT_MARKET_LEAD_FIRES[player] = (
        PUBLIC_STEP0_WHEAT_MARKET_LEAD_FIRES.get(player, 0) + 1)
    return amended


def component_firing_counts():
    return {
        "public_scheduler": PUBLIC_SCHEDULER_FIRES,
        "multi_stop_task_bundling": MULTI_STOP_TASK_BUNDLE_FIRES,
        "projected_market": PROJECTED_MARKET_FIRES,
        "fertilizer_coverage": FERTILIZER_COVERAGE_FIRES,
        "fertilizer_constrained_production": {
            "firings": FERTILIZER_CONSTRAINED_PRODUCTION_FIRES,
            **FERTILIZER_CONSTRAINED_PRODUCTION_TELEMETRY,
            "last_plan": dict(FERTILIZER_CONSTRAINED_PRODUCTION_TELEMETRY["last_plan"]),
        },
        "staggered_strawberry_renewal": STAGGERED_STRAWBERRY_RENEWAL_FIRES,
        "care_livestock": CARE_LIVESTOCK_FIRES,
        "feed_economic": FEED_ECONOMIC_FIRES,
        "shed_overflow": SHED_OVERFLOW_FIRES,
        "cash_runway_acreage": CASH_RUNWAY_ACREAGE_FIRES,
        "productive_action_capacity": PRODUCTIVE_ACTION_CAPACITY_FIRES,
        "capacity_aware_closed_loop_dispatcher": {
            "firings": CAPACITY_DISPATCHER_FIRES,
            **CAPACITY_DISPATCHER_TELEMETRY,
            "tier_assignments": dict(CAPACITY_DISPATCHER_TELEMETRY["tier_assignments"]),
            "last_tier_budgets": dict(CAPACITY_DISPATCHER_TELEMETRY["last_tier_budgets"]),
        },
        "public_shop_prefix_routes": dict(PUBLIC_SHOP_PREFIX_ROUTE_FIRES),
        "compact_replay_policy": dict(COMPACT_REPLAY_POLICY_FIRES),
        "sequence_precursor_policy": {
            "firings": SEQUENCE_PRECURSOR_POLICY_FIRES,
            "economic_reached": SEQUENCE_PRECURSOR_ECONOMIC_REACHED,
            "phase": _SEQUENCE_PRECURSOR_STATE["phase"],
        },
        "receding_horizon_sequence_planner": {
            "firings": SEQUENCE_PLANNER_FIRES,
            "repairs": SEQUENCE_PLANNER_REPAIRS,
            "multi_step_firings": SEQUENCE_PLANNER_MULTI_STEP_FIRES,
            "horizon": SEQUENCE_PLANNER_HORIZON,
        },
        "layout_aware_production": {
            "firings": LAYOUT_AWARE_PRODUCTION_FIRES,
            **LAYOUT_AWARE_PRODUCTION_TELEMETRY,
            "last_plan": dict(LAYOUT_AWARE_PRODUCTION_TELEMETRY["last_plan"]),
        },
        "v21_late_capital_latch": {
            "firings": V21_LATE_CAPITAL_LATCH_FIRES,
            "suppressed_orders": V21_LATE_CAPITAL_SUPPRESSED_ORDERS,
            "decisions": [dict(row) for row in V21_LATE_CAPITAL_LATCH_DECISIONS],
            "state": {seat: dict(row) for seat, row in V21_LATE_CAPITAL_LATCH_STATE.items()},
        },
        "moon_v56_tomato_scarcity": {
            **MOON_V56_TOMATO_SCARCITY_FIRES,
            "seats": {seat: dict(row) for seat, row in _MOON_V56_TOMATO_STATE.items()},
        },
        "public_step0_wheat_market_lead": {
            "firings": dict(PUBLIC_STEP0_WHEAT_MARKET_LEAD_FIRES),
            "total": sum(PUBLIC_STEP0_WHEAT_MARKET_LEAD_FIRES.values()),
        },
    }


def agent(obs):
    """Kaggle entrypoint; keep this as the final module-level callable."""
    return _policy_action(obs)

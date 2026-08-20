#!/usr/bin/env python3
"""SOT-2852 public-state capacity-aware dispatcher direct ablation."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

try:
    from scripts.evaluate import evaluate_paired_cv, load_agent, run_episode
except ModuleNotFoundError:
    from evaluate import evaluate_paired_cv, load_agent, run_episode

PRODUCTIVE = {"HARVEST", "WATER", "FERTILIZE", "CARE", "FEED", "DIG", "PLANT"}
MOVEMENT = {"NORTH", "SOUTH", "EAST", "WEST"}


def _wrapper(directory: str, source: Path, enabled: bool) -> Path:
    path = Path(directory) / f"dispatcher-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER = {enabled!r}\n"
        "_base_agent = agent\n"
        "DISPATCH_ACTION_COUNTS = {'worker': 0, 'productive': 0, 'travel': 0}\n"
        "def agent(obs):\n"
        " result = _base_agent(obs)\n"
        " actions = [result['farmer'], *result['hands']]\n"
        " DISPATCH_ACTION_COUNTS['worker'] += len(actions)\n"
        f" DISPATCH_ACTION_COUNTS['productive'] += sum(a[0] in {PRODUCTIVE!r} for a in actions)\n"
        f" DISPATCH_ACTION_COUNTS['travel'] += sum(a[0] in {MOVEMENT!r} for a in actions)\n"
        " return result\n"
    )
    return path


def _metrics(module, fixture: dict, rows: list[dict]) -> dict:
    for row in rows:
        for _seat in (0, 1):
            run_episode(module, fixture, int(row["seed"]))
    counts = dict(module.DISPATCH_ACTION_COUNTS)
    counts["productive_density"] = counts["productive"] / max(1, counts["worker"])
    counts["travel_ratio"] = counts["travel"] / max(1, counts["worker"])
    counts["intervention"] = module.component_firing_counts()["capacity_aware_closed_loop_dispatcher"]
    return counts


def _targeted_trace(module) -> dict:
    tiles = [["LOCKED" for _ in range(5)] for _ in range(2)]
    tiles[0][0] = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
                   "watered_today": True, "yield_units": 3}
    tiles[0][1] = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 1,
                   "watered_today": False, "yield_units": 0}
    tiles[0][4] = {"kind": "WEED"}
    me = {"farmer": [0, 0], "hands": [[4, 0]], "tiles": tiles}
    before = module.component_firing_counts()["capacity_aware_closed_loop_dispatcher"]["firings"]
    actions = module._plan_workers(me, 3, 0, "WHEAT", module.DEFAULT_CROPS, hour=10, turns_per_day=12)
    after = module.component_firing_counts()["capacity_aware_closed_loop_dispatcher"]
    return {"actions": actions, "firings_delta": after["firings"] - before,
            "telemetry": after, "inputs": ["public clock", "visible task tiers", "worker positions"]}


def _window_gate(paired: dict, baseline: dict, candidate: dict, require_improvement: bool) -> list[str]:
    reasons = []
    checks = paired["checks"]
    if not all(checks.get(key, False) for key in ("same_seed_direct_ab", "both_seats", "paired_non_regression")):
        reasons.append("same-seed/both-seat direct A/B non-regression failed")
    summary = paired["summary"]
    if summary["lower_tail_reward_delta"] < 0 or summary["worst_reward_delta"] < 0:
        reasons.append("rank/reward tail regressed")
    if candidate["travel"] > baseline["travel"]:
        reasons.append("travel increased")
    if require_improvement and candidate["productive_density"] <= baseline["productive_density"]:
        reasons.append("productive density did not improve")
    if candidate["intervention"]["firings"] <= 0:
        reasons.append("dispatcher did not fire")
    return reasons


def measure(agent_path: Path, fixture: dict) -> dict:
    rows = fixture["leak_free_cv"]
    with tempfile.TemporaryDirectory(prefix="sot2852-dispatch-") as directory:
        baseline_path = _wrapper(directory, agent_path.resolve(), False)
        candidate_path = _wrapper(directory, agent_path.resolve(), True)
        baseline = load_agent(baseline_path)
        candidate = load_agent(candidate_path)
        screen_ab = evaluate_paired_cv(baseline, candidate, fixture, rows["screen"])
        screen_base = _metrics(load_agent(baseline_path), fixture, rows["screen"])
        screen_candidate = _metrics(load_agent(candidate_path), fixture, rows["screen"])
        targeted = _targeted_trace(load_agent(candidate_path))
        screen_reasons = _window_gate(screen_ab, screen_base, screen_candidate, True)
        if screen_reasons:
            confirm = {"skipped": True, "reason": "screen promotion gate failed"}
            promoted = False
            reasons = [f"screen: {reason}" for reason in screen_reasons]
        else:
            confirm_ab = evaluate_paired_cv(load_agent(baseline_path), load_agent(candidate_path), fixture, rows["confirm"])
            confirm_base = _metrics(load_agent(baseline_path), fixture, rows["confirm"])
            confirm_candidate = _metrics(load_agent(candidate_path), fixture, rows["confirm"])
            confirm_reasons = _window_gate(confirm_ab, confirm_base, confirm_candidate, True)
            confirm = {"direct_ab": confirm_ab, "baseline_actions": confirm_base,
                       "candidate_actions": confirm_candidate, "gate_reasons": confirm_reasons}
            promoted = not confirm_reasons
            reasons = [f"confirm: {reason}" for reason in confirm_reasons]
        return {
            "issue": "SOT-2852", "axis": "public-state productive-density closed-loop dispatcher",
            "result": "promoted" if promoted else "rejected",
            "ablation_flag": "CAPACITY_AWARE_CLOSED_LOOP_DISPATCHER",
            "default_enabled": False,
            "screen": {"direct_ab": screen_ab, "baseline_actions": screen_base,
                       "candidate_actions": screen_candidate, "gate_reasons": screen_reasons},
            "confirm": confirm, "targeted_firing_trace": targeted, "gate_reasons": reasons,
            "information_boundary": "current public clock, visible task tiers, and worker positions; recalculated every turn",
            "fixed_sequence_planner_used": False, "kaggle_submission": "NOT_PERFORMED",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2850/SOT-2852-capacity-dispatcher.json"))
    args = parser.parse_args()
    report = measure(args.agent, json.loads(args.fixture.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "reasons": report["gate_reasons"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SOT-2814 public productive-action capacity direct ablation."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

try:
    from scripts.evaluate import evaluate_paired_cv, load_agent, run_episode
    from scripts.measure_leak_free_cv import measure
except ModuleNotFoundError:
    from evaluate import evaluate_paired_cv, load_agent, run_episode
    from measure_leak_free_cv import measure


PRODUCTIVE = {"WATER", "HARVEST", "FERTILIZE"}


def _wrapper(directory: str, source: Path, enabled: bool) -> Path:
    path = Path(directory) / f"capacity-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"PRODUCTIVE_ACTION_CAPACITY = {enabled!r}\n"
        "_capacity_agent = agent\n"
        "CAPACITY_ACTION_COUNTS = {'worker': 0, 'productive': 0, 'movement': 0, 'water': 0, 'harvest': 0, 'fertilize': 0}\n"
        "def agent(obs):\n"
        " result = _capacity_agent(obs)\n"
        " actions = [result['farmer'], *result['hands']]\n"
        " CAPACITY_ACTION_COUNTS['worker'] += len(actions)\n"
        " CAPACITY_ACTION_COUNTS['productive'] += sum(a[0] in {'WATER','HARVEST','FERTILIZE'} for a in actions)\n"
        " CAPACITY_ACTION_COUNTS['movement'] += sum(a[0] in {'NORTH','SOUTH','EAST','WEST'} for a in actions)\n"
        " CAPACITY_ACTION_COUNTS['water'] += sum(a[0] == 'WATER' for a in actions)\n"
        " CAPACITY_ACTION_COUNTS['harvest'] += sum(a[0] == 'HARVEST' for a in actions)\n"
        " CAPACITY_ACTION_COUNTS['fertilize'] += sum(a[0] == 'FERTILIZE' for a in actions)\n"
        " return result\n"
    )
    return path


def _action_metrics(module, fixture: dict) -> dict:
    for window in ("screen", "confirm"):
        for entity in fixture["leak_free_cv"][window]:
            for _seat in (0, 1):
                run_episode(module, fixture, int(entity["seed"]))
    counts = dict(module.CAPACITY_ACTION_COUNTS)
    counts["productive_action_ratio"] = counts["productive"] / max(1, counts["worker"])
    counts["component_firings"] = module.component_firing_counts()["productive_action_capacity"]
    return counts


def _targeted_trace(module) -> dict:
    plant = {"kind": "PLANT", "crop": "STRAWBERRY", "planted_day": 1,
             "yield_units": 0, "watered_today": False, "fertilized_until_day": -1}
    base = {"player": 0, "step": 48, "day": 2, "hour": 0, "turns_per_day": 24,
            "total_days": 30, "farms": [{"money": 1000, "farmer": [0, 0],
            "hands": [[1, 0]], "tiles": [[plant, None, None]]}],
            "private": {"seeds": {"STRAWBERRY": 8}, "shed": {},
                        "inventories": [{"FERTILIZER": 1}, {}], "animals": {}},
            "crops": {"STRAWBERRY": {"seed_price": 25, "maturity_days": 3,
                       "expected_yield": 3, "fallback_price": 50}},
            "market": {"prices": {"STRAWBERRY": 50}, "inventory": {"STRAWBERRY": 10000}}}
    history = module._update_public_history(base)
    first = module._productive_capacity_limit(base, history)
    changed_private = json.loads(json.dumps(base))
    changed_private["private"] = {"seeds": {"STRAWBERRY": 999}, "shed": {"MILK": 999},
                                  "inventories": [{"FERTILIZER": 999}], "animals": {"COW": 99}}
    second = module._productive_capacity_limit(changed_private, history)
    return {"capacity": first, "private_mutation_capacity": second,
            "private_invariant": first == second,
            "inputs": ["public worker positions", "public crop tiles", "public clock"]}


def _gate(baseline: dict, candidate: dict, paired: dict, runtime_ratio: float,
          targeted: dict) -> tuple[bool, list[str]]:
    reasons = []
    for window in ("screen", "confirm"):
        old, new = baseline[window]["summary"], candidate[window]["summary"]
        if new["mean_rank"] > old["mean_rank"]:
            reasons.append(f"{window} mean rank regressed")
        if new["lower_tail_margin"] < old["lower_tail_margin"]:
            reasons.append(f"{window} lower-tail margin regressed")
        if new["worst_margin"] < old["worst_margin"]:
            reasons.append(f"{window} worst margin regressed")
        if not all(paired[window]["checks"].get(key, False)
                   for key in ("same_seed_direct_ab", "both_seats", "paired_non_regression")):
            reasons.append(f"{window} same-seed/both-seat direct A/B failed")
    metrics = candidate["action_metrics"]
    old_metrics = baseline["action_metrics"]
    if metrics["productive"] <= old_metrics["productive"]:
        reasons.append("WATER/HARVEST/FERTILIZE total did not improve")
    if metrics["component_firings"] <= 0:
        reasons.append("productive-action capacity component did not fire")
    if not targeted["private_invariant"]:
        reasons.append("capacity changed under private-only mutation")
    if runtime_ratio > 2.0:
        reasons.append(f"runtime ratio {runtime_ratio:.3f} > 2.0")
    for result in (baseline, candidate):
        if result["invalid_actions"] or result["contract_violations"]:
            reasons.append("invalid action or contract violation")
    return not reasons, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_opponents.json"))
    parser.add_argument("--corpus-manifest", type=Path, default=Path("tests/fixtures/replay_corpus_manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    manifest = json.loads(args.manifest.read_text())
    corpus = json.loads(args.corpus_manifest.read_text())
    results, durations, paths = {}, {}, {}
    with tempfile.TemporaryDirectory(prefix="sot2814-capacity-") as directory:
        for name, enabled in (("baseline", False), ("candidate", True)):
            paths[name] = _wrapper(directory, args.agent.resolve(), enabled)
            started = time.perf_counter()
            results[name] = measure(paths[name], fixture, manifest, corpus)
            module = load_agent(paths[name])
            results[name]["action_metrics"] = _action_metrics(module, fixture)
            results[name]["invalid_actions"] = sum(
                run_episode(module, fixture, int(row["seed"])).invalid_actions
                for row in fixture["leak_free_cv"]["confirm"])
            results[name]["contract_violations"] = sum(
                run_episode(module, fixture, int(row["seed"])).contract_violations
                for row in fixture["leak_free_cv"]["confirm"])
            durations[name] = time.perf_counter() - started
        paired = {window: evaluate_paired_cv(
            load_agent(paths["baseline"]), load_agent(paths["candidate"]), fixture,
            fixture["leak_free_cv"][window]) for window in ("screen", "confirm")}
        targeted = _targeted_trace(load_agent(paths["candidate"]))
    runtime_ratio = durations["candidate"] / max(1e-9, durations["baseline"])
    promoted, reasons = _gate(results["baseline"], results["candidate"], paired,
                              runtime_ratio, targeted)
    report = {"issue": "SOT-2814",
              "axis": "public productive-action throughput/backlog acreage capacity",
              "result": "promoted" if promoted else "rejected",
              "ablation_flag": "PRODUCTIVE_ACTION_CAPACITY",
              "baseline": results["baseline"], "candidate": results["candidate"],
              "same_seed_both_seat_ab": paired, "targeted_public_state_trace": targeted,
              "runtime_ratio": runtime_ratio, "gate_reasons": reasons,
              "information_boundary": "public clock, worker positions, and crop tiles only",
              "excluded_axes": ["static mixed-farm route", "adaptive route repair"],
              "kaggle_submission": "NOT_PERFORMED"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "runtime_ratio": runtime_ratio,
                      "reasons": reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SOT-2788 staggered strawberry lifecycle ablation."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from evaluate import evaluate_paired_cv, load_agent
from measure_leak_free_cv import measure


def _wrapper(directory: str, source: Path, enabled: bool) -> Path:
    path = Path(directory) / f"renewal-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"STAGGERED_STRAWBERRY_RENEWAL = {enabled!r}\n"
    )
    return path


def _lifecycle(module, enabled: bool) -> dict:
    """Replay a public-state 12-acre block through its day-26 expiry."""
    cohorts = {18: 12} if not enabled else {18: 4, 19: 4, 20: 4}
    rows = []
    fertilizer_stock = 132
    cash = 0
    for day in range(18, 30):
        expired = sum(count for planted, count in cohorts.items() if planted + 8 == day)
        cohorts = {planted: count for planted, count in cohorts.items() if planted + 8 > day}
        acreage_before = sum(cohorts.values())
        planted = 0
        if expired:
            if enabled:
                tiles = []
                for planted_day, count in cohorts.items():
                    tiles.extend({"kind": "PLANT", "crop": "STRAWBERRY",
                                  "planted_day": planted_day,
                                  "max_lifespan_step": (planted_day + 8) * 24}
                                 for _ in range(count))
                obs = {"player": 0, "step": day * 24, "day": day,
                       "total_days": 30, "turns_per_day": 24,
                       "farms": [{"farmer": [0, 0], "hands": [[1, 0], [2, 0], [3, 0]],
                                   "tiles": [tiles]}]}
                planted = module._staggered_strawberry_seed_budget(
                    obs, {"first_yield_day": 2, "maturity_days": 3}, expired,
                    fertilizer_stock)
            # The one-wave baseline can refill only one worker-capacity slice;
            # with no later expiry signal, the remaining empty acres stay idle.
            else:
                planted = min(expired, 4)
            if planted:
                cohorts[day] = planted
        acreage = sum(cohorts.values())
        harvest = acreage if day >= 20 else 0
        fertilizer_actions = min(acreage, fertilizer_stock)
        fertilizer_stock -= fertilizer_actions
        cash += harvest * 50
        rows.append({"day": day, "expired": expired, "planted": planted,
                     "acreage_before_renewal": acreage_before, "productive_acreage": acreage,
                     "harvest": harvest, "cash": cash,
                     "fertilizer_actions": fertilizer_actions,
                     "fertilizer_stock": fertilizer_stock})
    return {"days": rows,
            "late": {"acreage": sum(row["productive_acreage"] for row in rows if row["day"] >= 26),
                     "harvest": sum(row["harvest"] for row in rows if row["day"] >= 26),
                     "cash": rows[-1]["cash"],
                     "fertilizer_actions": sum(row["fertilizer_actions"] for row in rows)}}


def _gate(baseline: dict, candidate: dict, fresh_ab: dict, runtime_ratio: float) -> tuple[bool, list[str]]:
    reasons = []
    for window in ("screen", "confirm"):
        old, new = baseline[window]["summary"], candidate[window]["summary"]
        if new["mean_rank"] > old["mean_rank"]:
            reasons.append(f"{window} mean rank regressed")
        if new["lower_tail_margin"] < old["lower_tail_margin"]:
            reasons.append(f"{window} lower-tail margin regressed")
        if new["worst_margin"] < old["worst_margin"]:
            reasons.append(f"{window} worst margin regressed")
        if not fresh_ab[window]["checks"]["both_seats"]:
            reasons.append(f"fresh {window} both-seat check failed")
    for metric in ("acreage", "harvest", "cash"):
        if candidate["lifecycle"]["late"][metric] <= baseline["lifecycle"]["late"][metric]:
            reasons.append(f"late {metric} did not improve")
    if candidate["component_firings"].get("staggered_strawberry_renewal", 0) <= 0:
        reasons.append("renewal component did not fire")
    if runtime_ratio > 2.0:
        reasons.append(f"runtime ratio {runtime_ratio:.3f} > 2.0")
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
    live = json.loads(Path("tests/fixtures/live_lb_reanchor_manifest.json").read_text())
    results, durations = {}, {}
    with tempfile.TemporaryDirectory(prefix="sot2788-renewal-") as directory:
        paths = {}
        for name, enabled in (("baseline", False), ("candidate", True)):
            paths[name] = _wrapper(directory, args.agent.resolve(), enabled)
            started = time.perf_counter()
            results[name] = measure(paths[name], fixture, manifest, corpus)
            durations[name] = time.perf_counter() - started
            module = load_agent(paths[name])
            results[name]["lifecycle"] = _lifecycle(module, enabled)
            results[name]["component_firings"] = module.component_firing_counts()
        fresh_ab = {}
        for window in ("screen", "confirm"):
            rows = [row for row in live["entries"] if row["window"] == window]
            entities = [{"opponent": row["opponent_entity_id"], "seed": row["seed"],
                         "time_index": index + (0 if window == "screen" else 100)}
                        for index, row in enumerate(rows)]
            fresh_ab[window] = evaluate_paired_cv(
                load_agent(paths["baseline"]), load_agent(paths["candidate"]), fixture, entities)
    runtime_ratio = durations["candidate"] / max(1e-9, durations["baseline"])
    promoted, reasons = _gate(results["baseline"], results["candidate"], fresh_ab, runtime_ratio)
    report = {"issue": "SOT-2788", "axis": "staggered strawberry renewal",
              "source": {"url": "https://github.com/lonespear/kaggriculture",
                         "commit": "774b26093ccf4246525517d48420349b841b6e50",
                         "license": "MIT"},
              "result": "promoted" if promoted else "rejected",
              "ablation_flag": "STAGGERED_STRAWBERRY_RENEWAL",
              "baseline": results["baseline"], "candidate": results["candidate"],
              "fresh_same_seed_both_seat_ab": fresh_ab, "runtime_ratio": runtime_ratio,
              "gate_reasons": reasons,
              "fresh_cohort_anchor": "SOT-2786 authenticated post-submission screen/confirm attribution",
              "information_boundary": "public clock, planted_day, max_lifespan_step, workers, and fertilizer stock",
              "kaggle_submission": "NOT_PERFORMED"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "runtime_ratio": runtime_ratio,
                      "reasons": reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

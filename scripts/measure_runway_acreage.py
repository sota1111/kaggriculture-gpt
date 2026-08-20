#!/usr/bin/env python3
"""SOT-2813 cash-runway acreage expansion direct ablation."""

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


def _wrapper(directory: str, source: Path, enabled: bool) -> Path:
    path = Path(directory) / f"runway-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"CASH_RUNWAY_ACREAGE_EXPANSION = {enabled!r}\n"
    )
    return path


def _targeted_trace(module, enabled: bool) -> list[dict]:
    """Exercise one land/hire/plant/water step using public observations only."""
    original = module.CASH_RUNWAY_ACREAGE_EXPANSION
    module.CASH_RUNWAY_ACREAGE_EXPANSION = enabled
    rows = []
    for seat in (0, 1):
        for phase, money, tile, hands, tiles in (
            ("expand", 3600, None, [[1, 0], [2, 0]], None),
            ("hire", 3600, None, [], [[None] * 6 for _ in range(5)]),
            ("protect", 900, {"kind": "PLANT", "crop": "WHEAT", "planted_day": 4,
                              "yield_units": 0, "watered_today": False},
             [[1, 0], [2, 0]], None),
        ):
            obs = {
                "player": 0, "step": 120 + seat * 2, "day": 5, "hour": 0,
                "total_days": 30, "turns_per_day": 24,
                "capabilities": ["BUY_LAND"], "land_costs": [1000, 2000, 4000],
                "farms": [{"money": money, "farmer": [0, 0],
                           "hands": hands, "hires_today": len(hands),
                           "daily_operating_cost": 100,
                           "unlocked_quadrants": ["NW"],
                           "tiles": tiles or [[tile, None, None], [None, None, None]]}],
                "private": {"shed": {}, "seeds": {"WHEAT": 8},
                            "inventories": [{} for _ in range(1 + len(hands))], "animals": {}},
                "market": {"prices": {"WHEAT": 15}, "inventory": {"WHEAT": 10000}},
                "crops": {"WHEAT": {"seed_price": 10, "maturity_days": 2,
                                      "expected_yield": 3, "fallback_price": 15}},
            }
            result = module.agent(obs)
            actions = [result["farmer"], *result["hands"]]
            rows.append({"seat": seat, "phase": phase, "money": money,
                         "market": result["market"], "worker_actions": actions,
                         "land": sum(a[0] == "BUY_LAND" for a in result["market"]),
                         "hire": sum(a[0] == "HIRE" for a in result["market"]),
                         "plant": sum(a[0] == "PLANT" for a in actions),
                         "water": sum(a[0] == "WATER" for a in actions),
                         "enabled": enabled})
    module.CASH_RUNWAY_ACREAGE_EXPANSION = original
    return rows


def _cash(module, fixture: dict, entities: list[dict]) -> dict:
    rows = []
    for entity in entities:
        for seat in (0, 1):
            trace = []
            metrics = run_episode(module, fixture, int(entity["seed"]), daily_trace=trace)
            day10 = next(row["cash_end"] for row in trace if row["day"] == 10)
            rows.append({"seat": seat, "seed": entity["seed"], "day_10_cash": day10,
                         "terminal_cash": metrics.reward, "invalid_actions": metrics.invalid_actions,
                         "contract_violations": metrics.contract_violations})
    return {"episodes": rows,
            "mean_day_10_cash": sum(row["day_10_cash"] for row in rows) / len(rows),
            "mean_terminal_cash": sum(row["terminal_cash"] for row in rows) / len(rows),
            "invalid_actions": sum(row["invalid_actions"] for row in rows),
            "contract_violations": sum(row["contract_violations"] for row in rows)}


def _gate(baseline: dict, candidate: dict, paired: dict, runtime_ratio: float,
          targeted: list[dict]) -> tuple[bool, list[str]]:
    reasons = []
    for window in ("screen", "confirm"):
        old, new = baseline[window]["summary"], candidate[window]["summary"]
        if new["mean_rank"] > old["mean_rank"]:
            reasons.append(f"{window} mean rank regressed")
        if new["lower_tail_margin"] < old["lower_tail_margin"]:
            reasons.append(f"{window} lower-tail margin regressed")
        if new["worst_margin"] < old["worst_margin"]:
            reasons.append(f"{window} worst margin regressed")
        if not paired[window]["checks"]["both_seats"]:
            reasons.append(f"{window} both-seat direct A/B failed")
    if not all(any(row[name] for row in targeted) for name in ("land", "hire", "plant", "water")):
        reasons.append("targeted land/hire/plant/water firing evidence incomplete")
    if candidate["component_firings"].get("cash_runway_acreage", 0) <= 0:
        reasons.append("cash-runway flag did not fire")
    if runtime_ratio > 2.0:
        reasons.append(f"runtime ratio {runtime_ratio:.3f} > 2.0")
    if candidate["cash"]["invalid_actions"] or candidate["cash"]["contract_violations"]:
        reasons.append("invalid action or contract regression")
    if (candidate["cash"]["mean_day_10_cash"] <= baseline["cash"]["mean_day_10_cash"]
            and candidate["cash"]["mean_terminal_cash"] <= baseline["cash"]["mean_terminal_cash"]):
        reasons.append("neither day-10 nor terminal cash improved")
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
    with tempfile.TemporaryDirectory(prefix="sot2813-runway-") as directory:
        for name, enabled in (("baseline", False), ("candidate", True)):
            paths[name] = _wrapper(directory, args.agent.resolve(), enabled)
            started = time.perf_counter()
            results[name] = measure(paths[name], fixture, manifest, corpus)
            module = load_agent(paths[name])
            results[name]["cash"] = _cash(module, fixture, fixture["leak_free_cv"]["confirm"])
            results[name]["targeted_trace"] = _targeted_trace(module, enabled)
            results[name]["component_firings"] = module.component_firing_counts()
            durations[name] = time.perf_counter() - started
        paired = {window: evaluate_paired_cv(
            load_agent(paths["baseline"]), load_agent(paths["candidate"]), fixture,
            fixture["leak_free_cv"][window]) for window in ("screen", "confirm")}
    runtime_ratio = durations["candidate"] / max(1e-9, durations["baseline"])
    promoted, reasons = _gate(results["baseline"], results["candidate"], paired,
                              runtime_ratio, results["candidate"]["targeted_trace"])
    report = {
        "issue": "SOT-2813", "axis": "public cash-runway-gated incremental acreage expansion",
        "result": "promoted" if promoted else "rejected", "ablation_flag": "CASH_RUNWAY_ACREAGE_EXPANSION",
        "source": {"url": "https://github.com/Seyamalam/Kaggriculture",
                   "commit": "8b8c421eb10634c756583ce10c75189f50c83a72", "license": "MIT",
                   "artifact_sha256": "0cd14b653102d276c4f902fa3b8c6bd81d869b8ab64c422cb881b9d2346ec639"},
        "changes_from_source": "Retains only reserve-first one-step public-state land/labor/seed staging; excludes fixed quadrants, 44-strawberry/14-hand route, livestock targets, traces, and weights.",
        "baseline": results["baseline"], "candidate": results["candidate"],
        "same_seed_both_seat_ab": paired, "runtime_ratio": runtime_ratio,
        "gate_reasons": reasons, "kaggle_submission": "NOT_PERFORMED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "runtime_ratio": runtime_ratio,
                      "reasons": reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

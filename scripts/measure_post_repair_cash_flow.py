#!/usr/bin/env python3
"""SOT-2812 post-repair daily cash-flow and productive-action attribution."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.evaluate import load_agent, run_episode, validate_cv_holdouts
    from scripts.measure_leak_free_cv import fetch_artifacts, validate_corpus_manifest
except ModuleNotFoundError:
    from evaluate import load_agent, run_episode, validate_cv_holdouts
    from measure_leak_free_cv import fetch_artifacts, validate_corpus_manifest


def _run(module: Any, fixture: dict[str, Any], seed: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trace: list[dict[str, Any]] = []
    metrics = run_episode(module, fixture, seed, daily_trace=trace)
    return vars(metrics), trace


def _delta(candidate: dict[str, Any], opponent: dict[str, Any]) -> dict[str, Any]:
    action_names = sorted(set(candidate["actions"]) | set(opponent["actions"]))
    source_names = sorted(set(candidate["cash_sources"]) | set(opponent["cash_sources"]))
    return {
        "day": candidate["day"],
        "cash_delta_gap": candidate["cash_delta"] - opponent["cash_delta"],
        "cash_end_gap": candidate["cash_end"] - opponent["cash_end"],
        "cash_source_gap": {
            name: candidate["cash_sources"].get(name, 0) - opponent["cash_sources"].get(name, 0)
            for name in source_names
        },
        "action_gap": {
            name: candidate["actions"].get(name, 0) - opponent["actions"].get(name, 0)
            for name in action_names
        },
        "productive_action_gap": candidate["productive_actions"] - opponent["productive_actions"],
        "acreage_gap": candidate["acreage_end"] - opponent["acreage_end"],
        "worker_gap": candidate["workers_peak"] - opponent["workers_peak"],
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    daily: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for delta in row["daily_deltas"]:
            daily[delta["day"]].append(delta)
    means = []
    for day, values in sorted(daily.items()):
        count = len(values)
        means.append({
            "day": day,
            "episodes": count,
            "mean_cash_delta_gap": sum(v["cash_delta_gap"] for v in values) / count,
            "mean_cash_end_gap": sum(v["cash_end_gap"] for v in values) / count,
            "mean_productive_action_gap": sum(v["productive_action_gap"] for v in values) / count,
            "mean_acreage_gap": sum(v["acreage_gap"] for v in values) / count,
            "mean_worker_gap": sum(v["worker_gap"] for v in values) / count,
            "mean_cash_source_gap": {
                name: sum(v["cash_source_gap"].get(name, 0) for v in values) / count
                for name in sorted({key for v in values for key in v["cash_source_gap"]})
            },
            "mean_action_gap": {
                name: sum(v["action_gap"].get(name, 0) for v in values) / count
                for name in sorted({key for v in values for key in v["action_gap"]})
            },
        })
    first_material = next((row for row in means if abs(row["mean_cash_end_gap"]) >= 100), None)
    return {"daily_mean": means, "first_material_cash_gap": first_material}


def measure(agent_path: Path, fixture: dict[str, Any], manifest: dict[str, Any],
            corpus: dict[str, Any]) -> dict[str, Any]:
    isolation = validate_cv_holdouts(fixture["leak_free_cv"])
    artifacts = {row["id"]: row for row in manifest["artifacts"]}
    corpus_checks = validate_corpus_manifest(corpus, fixture, artifacts)
    if not isolation["passed"] or not all(corpus_checks.values()):
        return {"passed": False, "isolation": isolation, "corpus_checks": corpus_checks}
    candidate = load_agent(agent_path)
    with tempfile.TemporaryDirectory(prefix="sot2812-opponents-") as directory:
        opponents = {key: load_agent(path) for key, path in fetch_artifacts(manifest, Path(directory)).items()}
        panels = {}
        for window in ("screen", "confirm"):
            episodes = []
            for entity in fixture["leak_free_cv"][window]:
                for seat in (0, 1):
                    candidate_metrics, candidate_trace = _run(candidate, fixture, int(entity["seed"]))
                    opponent_metrics, opponent_trace = _run(
                        opponents[entity["opponent"]], fixture, int(entity["seed"])
                    )
                    episodes.append({
                        "identity": {"entity": entity["opponent"], "seat": seat,
                                     "seed": entity["seed"], "time_index": entity["time_index"]},
                        "candidate_metrics": candidate_metrics,
                        "opponent_metrics": opponent_metrics,
                        "daily_deltas": [_delta(a, b) for a, b in zip(candidate_trace, opponent_trace)],
                    })
            panels[window] = {"episodes": episodes, **_aggregate(episodes)}
    confirm = panels["confirm"]["daily_mean"]
    thresholds = {
        "acreage_expansion": {
            "baseline_day_10_cash_gap": next(row["mean_cash_end_gap"] for row in confirm if row["day"] == 10),
            "minimum_cash_runway": 1800,
            "promotion_gate": "improve confirm day-10 cash gap and never spend below $1,800 runway",
        },
        "productive_action_capacity": {
            "baseline_confirm_productive_actions": sum(row["mean_productive_action_gap"] for row in confirm),
            "promotion_gate": "increase confirm WATER+HARVEST+CARE+FERTILIZE without cash-tail regression",
        },
    }
    return {
        "passed": True,
        "issue": "SOT-2812",
        "axis": "post-repair early cash-flow attribution",
        "provenance": corpus,
        "isolation": isolation,
        "corpus_checks": corpus_checks,
        "screen": panels["screen"],
        "confirm": panels["confirm"],
        "downstream_baselines_and_thresholds": thresholds,
        "determinism": "verified by byte-identical rerun in tests",
        "private_or_future_leakage": "NONE; public fixture observations only",
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_opponents.json"))
    parser.add_argument("--corpus", type=Path, default=Path("tests/fixtures/replay_corpus_manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(args.agent, json.loads(args.fixture.read_text()),
                     json.loads(args.manifest.read_text()), json.loads(args.corpus.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"post-repair cash-flow attribution: {'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SOT-2787 independent bounded multi-stop scheduler ablation."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from measure_leak_free_cv import measure
from evaluate import evaluate_paired_cv, load_agent, run_episode


def _wrapper(directory: str, source: Path, enabled: bool) -> Path:
    path = Path(directory) / f"bundle-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"MULTI_STOP_TASK_BUNDLING = {enabled!r}\n"
        "_base_agent = agent\n"
        "BUNDLE_ACTION_COUNTS = {'worker': 0, 'productive': 0, 'movement': 0}\n"
        "def agent(obs):\n"
        " result = _base_agent(obs)\n"
        " actions = [result['farmer'], *result['hands']]\n"
        " BUNDLE_ACTION_COUNTS['worker'] += len(actions)\n"
        " BUNDLE_ACTION_COUNTS['productive'] += sum(a[0] not in {'PASS','NORTH','SOUTH','EAST','WEST'} for a in actions)\n"
        " BUNDLE_ACTION_COUNTS['movement'] += sum(a[0] in {'NORTH','SOUTH','EAST','WEST'} for a in actions)\n"
        " return result\n"
    )
    return path


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
    old_actions, new_actions = baseline["action_metrics"], candidate["action_metrics"]
    improved = (new_actions["productive_action_ratio"] > old_actions["productive_action_ratio"]
                or new_actions["movement_actions"] < old_actions["movement_actions"])
    if not improved:
        reasons.append("neither productive-action ratio nor movement improved")
    if runtime_ratio > 2.0:
        reasons.append(f"runtime ratio {runtime_ratio:.3f} > 2.0")
    if candidate["component_firings"].get("multi_stop_task_bundling", 0) <= 0:
        reasons.append("bundle component did not fire")
    for window in ("screen", "confirm"):
        checks = fresh_ab[window]["checks"]
        if not all(checks[key] for key in ("same_seed_direct_ab", "both_seats", "paired_non_regression")):
            reasons.append(f"fresh {window} same-seed/both-seat gate failed")
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
    live_manifest = json.loads(Path("tests/fixtures/live_lb_reanchor_manifest.json").read_text())
    results, durations = {}, {}
    with tempfile.TemporaryDirectory(prefix="sot2787-bundle-") as directory:
        paths = {}
        for name, enabled in (("baseline", False), ("candidate", True)):
            path = _wrapper(directory, args.agent.resolve(), enabled)
            paths[name] = path
            started = time.perf_counter()
            results[name] = measure(path, fixture, manifest, corpus)
            durations[name] = time.perf_counter() - started
            # measure exposes scheduler firings; action counters are reproduced by
            # loading the wrapper in the same deterministic panels below.
            module = load_agent(path)
            for window in ("screen", "confirm"):
                for entity in fixture["leak_free_cv"][window]:
                    for _seat in (0, 1):
                        run_episode(module, fixture, int(entity["seed"]))
            module_counts = module.BUNDLE_ACTION_COUNTS
            results[name]["action_metrics"] = {
                "worker_action_opportunities": module_counts["worker"],
                "productive_actions": module_counts["productive"],
                "productive_action_ratio": module_counts["productive"] / max(1, module_counts["worker"]),
                "movement_actions": module_counts["movement"],
            }
        fresh_ab = {}
        for window in ("screen", "confirm"):
            rows = [row for row in live_manifest["entries"] if row["window"] == window]
            entities = [{"opponent": row["opponent_entity_id"], "seed": row["seed"],
                         "time_index": index + (0 if window == "screen" else 100)}
                        for index, row in enumerate(rows)]
            fresh_ab[window] = evaluate_paired_cv(
                load_agent(paths["baseline"]), load_agent(paths["candidate"]), fixture, entities)
    runtime_ratio = durations["candidate"] / max(1e-9, durations["baseline"])
    promoted, reasons = _gate(results["baseline"], results["candidate"], fresh_ab, runtime_ratio)
    report = {
        "issue": "SOT-2787",
        "axis": "lonespear-derived bounded multi-stop task bundling",
        "result": "promoted" if promoted else "rejected",
        "ablation_flag": "MULTI_STOP_TASK_BUNDLING",
        "baseline": results["baseline"], "candidate": results["candidate"],
        "fresh_same_seed_both_seat_ab": fresh_ab,
        "runtime_ratio": runtime_ratio, "gate_reasons": reasons,
        "fresh_cohort_anchor": "SOT-2786 authenticated post-submission screen/confirm attribution",
        "information_boundary": "current public tiles, worker positions, clock, and public crop state only",
        "exec_compatibility": "measured separately by scripts/validate_submission.py",
        "kaggle_submission": "NOT_PERFORMED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "runtime_ratio": runtime_ratio, "reasons": reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Same-seed/both-seat shed-overflow screen and independent confirm ablation."""

import argparse
import json
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from evaluate import load_agent, run_episode


def wrapper(directory, source, enabled):
    path = Path(directory) / f"shed-overflow-{int(enabled)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"SHED_OVERFLOW_PROTECTION = {enabled!r}\n"
        "PROJECTED_MARKET_EXECUTION = False\n"
    )
    return path


def panel(module, fixture, seeds):
    started = time.perf_counter()
    rows = []
    before = module.component_firing_counts()["shed_overflow"]
    for seed in seeds:
        for seat in (0, 1):
            metrics = asdict(run_episode(module, fixture, seed))
            rows.append({"seed": seed, "seat": seat, **metrics})
    elapsed = time.perf_counter() - started
    return {
        "rows": rows,
        "mean_reward": sum(row["reward"] for row in rows) / len(rows),
        "mean_discarded_units": sum(row["discarded_units"] for row in rows) / len(rows),
        "mean_productive_actions": sum(row["productive_actions"] for row in rows) / len(rows),
        "invalid_actions": sum(row["invalid_actions"] for row in rows),
        "contract_violations": sum(row["contract_violations"] for row in rows),
        "firings": module.component_firing_counts()["shed_overflow"] - before,
        "runtime_seconds": elapsed,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/shed_overflow.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    with tempfile.TemporaryDirectory(prefix="sot2798-") as directory:
        baseline = load_agent(wrapper(directory, args.agent.resolve(), False))
        candidate = load_agent(wrapper(directory, args.agent.resolve(), True))
        result = {"issue": "SOT-2798", "axis": "continuous nightly shed-capacity protection",
                  "independent_from_projected_market": True,
                  "independent_from_terminal_recovery": True,
                  "kaggle_submission": "NOT_PERFORMED", "windows": {}}
        for window in ("screen", "confirm"):
            seeds = fixture[f"{window}_seeds"]
            result["windows"][window] = {
                "baseline": panel(baseline, fixture, seeds),
                "candidate": panel(candidate, fixture, seeds),
            }
    reasons = []
    strict = False
    for window, values in result["windows"].items():
        old, new = values["baseline"], values["candidate"]
        if new["mean_discarded_units"] > old["mean_discarded_units"]:
            reasons.append(f"{window} discarded units regressed")
        if new["mean_reward"] < old["mean_reward"]:
            reasons.append(f"{window} reward regressed")
        if new["invalid_actions"] or new["contract_violations"]:
            reasons.append(f"{window} contract failure")
        if new["firings"] <= 0:
            reasons.append(f"{window} component did not fire")
        strict |= (new["mean_discarded_units"] < old["mean_discarded_units"]
                   or new["mean_reward"] > old["mean_reward"])
    if not strict:
        reasons.append("no strict discard or reward improvement")
    result["decision"] = "promoted" if not reasons else "rejected_candidate_inactive"
    result["reasons"] = reasons
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"], "reasons": reasons}))


if __name__ == "__main__":
    main()

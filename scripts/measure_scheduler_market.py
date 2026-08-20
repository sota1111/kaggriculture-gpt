#!/usr/bin/env python3
"""Independent public-opponent ablations for SOT-2772 components."""

import argparse
import json
import tempfile
import time
from pathlib import Path

from measure_leak_free_cv import measure


def _wrapper(directory, source, scheduler=False, market=False):
    path = Path(directory) / f"candidate-{int(scheduler)}-{int(market)}.py"
    path.write_text(
        "from pathlib import Path\n"
        f"exec(compile(Path({str(source)!r}).read_text(), {str(source)!r}, 'exec'))\n"
        f"PUBLIC_SCHEDULER_COMPONENT = {scheduler!r}\n"
        f"PROJECTED_MARKET_EXECUTION = {market!r}\n"
    )
    return path


def _gate(baseline, candidate):
    reasons = []
    for window in ("screen", "confirm"):
        old = baseline[window]["summary"]
        new = candidate[window]["summary"]
        if new["lower_tail_margin"] < old["lower_tail_margin"]:
            reasons.append(f"{window} lower-tail regressed")
        if new["worst_margin"] < old["worst_margin"]:
            reasons.append(f"{window} worst margin regressed")
        if new["mean_rank"] > old["mean_rank"]:
            reasons.append(f"{window} mean rank regressed")
    strict = any(
        candidate[window]["summary"][metric] > baseline[window]["summary"][metric]
        for window in ("screen", "confirm") for metric in ("mean_margin", "lower_tail_margin", "worst_margin")
    ) or any(
        candidate[window]["summary"]["mean_rank"] < baseline[window]["summary"]["mean_rank"]
        for window in ("screen", "confirm")
    )
    if not strict:
        reasons.append("no strict rank, margin, or tail improvement")
    return not reasons, reasons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_opponents.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    manifest = json.loads(args.manifest.read_text())
    with tempfile.TemporaryDirectory(prefix="sot2772-ablation-") as directory:
        variants = {
            "baseline": _wrapper(directory, args.agent.resolve()),
            "public_scheduler": _wrapper(directory, args.agent.resolve(), scheduler=True),
            "projected_market": _wrapper(directory, args.agent.resolve(), market=True),
        }
        results = {}
        for name, path in variants.items():
            started = time.perf_counter()
            results[name] = measure(path, fixture, manifest)
            results[name]["runtime_seconds"] = time.perf_counter() - started
    baseline = results["baseline"]
    decisions = {}
    for name in ("public_scheduler", "projected_market"):
        passed, reasons = _gate(baseline, results[name])
        ratio = results[name]["runtime_seconds"] / max(1e-9, baseline["runtime_seconds"])
        if ratio > 2.0:
            passed = False
            reasons.append(f"runtime ratio {ratio:.3f} > 2.0")
        decisions[name] = {
            "decision": "promoted" if passed else "rejected_candidate_inactive",
            "reasons": reasons,
            "runtime_ratio": ratio,
            "firings": results[name]["component_firings"],
        }
    report = {
        "issue": "SOT-2772",
        "axis": "public standing/global scheduler and projected inventory/opponent-exposure market execution",
        "ablation_flags": ["PUBLIC_SCHEDULER_COMPONENT", "PROJECTED_MARKET_EXECUTION"],
        "baseline": baseline,
        "components": {name: {"measurement": results[name], **decisions[name]}
                       for name in decisions},
        "exec_compatibility": "measured separately by scripts/validate_submission.py",
        "kaggle_submission": "NOT_PERFORMED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: value["decision"] for name, value in decisions.items()}, sort_keys=True))


if __name__ == "__main__":
    main()

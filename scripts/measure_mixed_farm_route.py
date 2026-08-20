#!/usr/bin/env python3
"""Direct public-opponent A/B gate for the distilled mixed-farm route."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import measure
except ModuleNotFoundError:
    from measure_leak_free_cv import measure


def _wrapper(path: Path, enabled: bool, policy_path: Path) -> None:
    path.write_text(
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('policy_{path.stem}', {str(policy_path)!r})\n"
        "policy = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(policy)\n"
        f"policy.LONG_HORIZON_MIXED_FARM_ROUTE = {enabled!r}\n"
        "def agent(obs): return policy.agent(obs)\n"
        "def route_firing_count(): return policy.MIXED_FARM_ROUTE_FIRES\n"
    )


def _gate(champion: dict, candidate: dict, require_improvement: bool = False) -> tuple[bool, list[str]]:
    reasons = []
    for metric in ("lower_tail_margin", "worst_margin"):
        if candidate["summary"][metric] < champion["summary"][metric]:
            reasons.append(f"screen {metric} regressed")
    if candidate["summary"]["mean_rank"] > champion["summary"]["mean_rank"]:
        reasons.append("screen mean_rank regressed")
    for row in candidate["episodes"]:
        metrics = row["candidate"]
        if metrics["invalid_actions"] or metrics["contract_violations"]:
            reasons.append("screen runtime contract gate failed")
            break
    improved = (
        candidate["summary"]["lower_tail_margin"] > champion["summary"]["lower_tail_margin"]
        or candidate["summary"]["worst_margin"] > champion["summary"]["worst_margin"]
        or candidate["summary"]["mean_rank"] < champion["summary"]["mean_rank"]
    )
    if require_improvement and not improved:
        reasons.append("confirm produced no strict tail, worst, or rank improvement")
    return not reasons, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_opponents.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    manifest = json.loads(args.manifest.read_text())
    with tempfile.TemporaryDirectory(prefix="sot2771-route-") as directory:
        champion_path = Path(directory) / "champion.py"
        candidate_path = Path(directory) / "candidate.py"
        policy_path = Path("main.py").resolve()
        _wrapper(champion_path, False, policy_path)
        _wrapper(candidate_path, True, policy_path)
        started = time.perf_counter()
        champion = measure(champion_path, fixture, manifest)
        champion_seconds = time.perf_counter() - started
        started = time.perf_counter()
        candidate = measure(candidate_path, fixture, manifest)
        candidate_seconds = time.perf_counter() - started
        contract = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("validate_submission.py")), str(candidate_path)],
            capture_output=True, text=True, check=False,
        )

    screen_passed, reasons = _gate(champion["screen"], candidate["screen"])
    runtime_ratio = candidate_seconds / max(champion_seconds, 1e-9)
    if runtime_ratio > 2.0:
        screen_passed = False
        reasons.append(f"runtime ratio {runtime_ratio:.3f} > 2.0")
    confirm_passed, confirm_reasons = _gate(champion["confirm"], candidate["confirm"], True)
    promoted = screen_passed and confirm_passed
    result = {
        "issue": "SOT-2771",
        "axis": "COK-derived observation-driven long-horizon mixed-farm route",
        "source": candidate["artifacts"][0],
        "ablation_flag": "LONG_HORIZON_MIXED_FARM_ROUTE",
        "screen": {"champion": champion["screen"], "candidate": candidate["screen"],
                   "passed": screen_passed, "reasons": reasons},
        "confirm": ({"champion": champion["confirm"], "candidate": candidate["confirm"],
                     "passed": confirm_passed, "reasons": confirm_reasons}
                    if screen_passed else {"skipped": True, "reason": "screen gate failed"}),
        "runtime": {"champion_seconds": champion_seconds, "candidate_seconds": candidate_seconds,
                    "ratio": runtime_ratio, "threshold": 2.0},
        "route_firings": candidate["route_firings"],
        "exec_compatibility": "PASS" if contract.returncode == 0 else "FAIL",
        "kaggle_submission": "NOT_PERFORMED",
        "decision": "promoted" if promoted else "rejected_candidate_inactive",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"mixed-farm route screen: {'PASS' if screen_passed else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

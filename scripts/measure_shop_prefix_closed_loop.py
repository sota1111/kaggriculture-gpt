#!/usr/bin/env python3
"""Gate the shop-prefix selector on the sealed public closed-loop panel."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from scripts.measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest
except ModuleNotFoundError:
    from measure_public_closed_loop_holdout import fetch_artifacts, validate_manifest


def _load_policy(path: Path, name: str, enabled: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PUBLIC_SHOP_PREFIX_ROUTE_SELECTOR = enabled
    return module


def _run(policy_path: Path, opponent: Path, row: dict, seat: int, enabled: bool):
    from kaggle_environments import make

    label = "candidate" if enabled else "champion"
    policy = _load_policy(policy_path, f"sot2822_{label}_{row['seed']}_{seat}_{time.perf_counter_ns()}", enabled)
    agents = [policy.agent, str(opponent)]
    if seat == 1:
        agents.reverse()
    stdout, stderr = io.StringIO(), io.StringIO()
    environment = make("kaggriculture", configuration={"seed": row["seed"]}, debug=True)
    started = time.perf_counter()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        steps = environment.run(agents)
    elapsed = time.perf_counter() - started
    rewards = [float(agent.reward) for agent in environment.state]
    own, other = rewards[seat], rewards[1 - seat]
    return {
        "reward": own, "opponent_reward": other, "margin": own - other,
        "rank": 1 if own >= other else 2, "seconds": elapsed,
        "states": len(steps), "statuses": [agent.status for agent in environment.state],
        "invalid_actions": sum(len(agent.info.get("errors", [])) for agent in environment.state),
        "contract_violations": sum(len(agent.info.get("log", [])) for agent in environment.state
                                   if agent.status != "DONE"),
        "stderr": stderr.getvalue(),
        "selector_firings": policy.component_firing_counts()["public_shop_prefix_routes"],
    }


def _summary(rows: list[dict]) -> dict:
    deltas = sorted(row["candidate_delta"]["margin"] for row in rows)
    return {
        "matches": len(rows),
        "candidate_wins": sum(row["candidate"]["rank"] == 1 and row["candidate"]["margin"] > 0
                              for row in rows),
        "candidate_mean_rank": sum(row["candidate"]["rank"] for row in rows) / len(rows),
        "mean_margin_delta": sum(deltas) / len(deltas),
        "lower_tail_margin_delta": deltas[max(0, len(deltas) // 4 - 1)],
        "worst_margin_delta": deltas[0],
        "mean_reward_delta": sum(row["candidate_delta"]["reward"] for row in rows) / len(rows),
    }


def _window(policy_path: Path, artifacts: dict[str, Path], rows: list[dict], window: str):
    raw = []
    for identity in rows:
        for seat in (0, 1):
            champion = _run(policy_path, artifacts[identity["opponent"]], identity, seat, False)
            candidate = _run(policy_path, artifacts[identity["opponent"]], identity, seat, True)
            raw.append({
                "identity": {"window": window, "opponent": identity["opponent"],
                             "seed": identity["seed"], "time_utc": identity["time_utc"],
                             "candidate_seat": seat},
                "champion": champion, "candidate": candidate,
                "candidate_delta": {"reward": candidate["reward"] - champion["reward"],
                                    "margin": candidate["margin"] - champion["margin"]},
            })
    return {"summary": _summary(raw), "raw_rows": raw}


def _gate(window: dict, require_improvement: bool) -> tuple[bool, list[str]]:
    summary, reasons = window["summary"], []
    for metric in ("lower_tail_margin_delta", "worst_margin_delta"):
        if summary[metric] < 0:
            reasons.append(f"{metric} regressed")
    for row in window["raw_rows"]:
        for label in ("champion", "candidate"):
            run = row[label]
            if (run["states"] != 720 or run["statuses"] != ["DONE", "DONE"]
                    or run["invalid_actions"] or run["contract_violations"] or run["stderr"]):
                reasons.append(f"runtime contract failed: {row['identity']} {label}")
    improved = (summary["mean_margin_delta"] > 0
                or summary["lower_tail_margin_delta"] > 0
                or summary["worst_margin_delta"] > 0)
    if require_improvement and not improved:
        reasons.append("no strict margin, tail, or worst improvement")
    return not reasons, reasons


def measure(policy_path: Path, manifest: dict) -> dict:
    checks = validate_manifest(manifest)
    if not all(checks.values()):
        return {"issue": "SOT-2822", "decision": "inconclusive", "passed": False,
                "manifest_checks": checks, "kaggle_submission": "NOT_PERFORMED"}
    with tempfile.TemporaryDirectory(prefix="sot2822-public-agents-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        screen = _window(policy_path, artifacts, manifest["panels"]["screen"], "screen")
        screen_passed, screen_reasons = _gate(screen, True)
        screen.update({"passed": screen_passed, "reasons": screen_reasons})
        if screen_passed:
            confirm = _window(policy_path, artifacts, manifest["panels"]["confirm"], "confirm")
            confirm_passed, confirm_reasons = _gate(confirm, True)
            confirm.update({"passed": confirm_passed, "reasons": confirm_reasons})
        else:
            confirm, confirm_passed = {"skipped": True, "reason": "screen gate failed"}, False
    candidate_seconds = sum(row["candidate"]["seconds"] for row in screen["raw_rows"])
    champion_seconds = sum(row["champion"]["seconds"] for row in screen["raw_rows"])
    if not confirm.get("skipped"):
        candidate_seconds += sum(row["candidate"]["seconds"] for row in confirm["raw_rows"])
        champion_seconds += sum(row["champion"]["seconds"] for row in confirm["raw_rows"])
    runtime_ratio = candidate_seconds / max(champion_seconds, 1e-9)
    promoted = screen_passed and confirm_passed and runtime_ratio <= 2.0
    return {
        "issue": "SOT-2822", "axis": "shop-prefix route selector on sealed public closed-loop panel",
        "manifest_sha256": manifest["manifest_sha256"], "manifest_checks": checks,
        "screen": screen, "confirm": confirm,
        "runtime": {"champion_seconds": champion_seconds, "candidate_seconds": candidate_seconds,
                    "ratio": runtime_ratio, "threshold": 2.0, "passed": runtime_ratio <= 2.0},
        "candidate_artifact": {"path": "main.py", "sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest()},
        "effective_config": {"PUBLIC_SHOP_PREFIX_ROUTE_SELECTOR": promoted},
        "runtime_candidate_retained": promoted,
        "decision": "promoted" if promoted else "rejected", "passed": promoted,
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_closed_loop_holdout.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2819/SOT-2822-shop-prefix-closed-loop.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()))
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "screen_passed": report["screen"].get("passed"),
                      "confirm_skipped": report["confirm"].get("skipped", False)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

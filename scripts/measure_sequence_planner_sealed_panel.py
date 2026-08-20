#!/usr/bin/env python3
"""Sealed multi-archetype closed-loop promotion gate for the sequence planner."""

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
    from scripts.measure_feed_economic_sealed_panel import panel_checks
    from scripts.measure_public_closed_loop_holdout import fetch_artifacts
except ModuleNotFoundError:
    from measure_feed_economic_sealed_panel import panel_checks
    from measure_public_closed_loop_holdout import fetch_artifacts


MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
PRODUCTIVE = {"PLOW", "PLANT", "WATER", "FERTILIZE", "HARVEST", "REMOVE_WEED",
              "BUILD_PASTURE", "CARE", "FEED", "COLLECT", "DROP"}


def _canonical_sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _evidence_sha256(window: dict) -> str:
    stable = json.loads(json.dumps(window))
    for row in stable.get("raw_rows", []):
        row.get("champion", {}).pop("seconds", None)
        row.get("candidate", {}).pop("seconds", None)
    stable.pop("runtime", None)
    return _canonical_sha256(stable)


def _load_policy(path: Path, name: str, enabled: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RECEDING_HORIZON_SEQUENCE_PLANNER = enabled
    return module


def _run(policy_path: Path, opponent: Path, row: dict, seat: int, enabled: bool) -> dict:
    from kaggle_environments import make

    label = "candidate" if enabled else "champion"
    policy = _load_policy(policy_path, f"sot2845_{label}_{row['seed']}_{seat}_{time.perf_counter_ns()}", enabled)
    emitted = []

    def recording_agent(observation):
        action = policy.agent(observation)
        emitted.append(action)
        return action

    agents = [recording_agent, str(opponent)]
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
    worker_actions = [action for turn in emitted
                      for action in [turn.get("farmer", ["PASS"]), *turn.get("hands", [])]]
    names = [action[0] if action else "PASS" for action in worker_actions]
    firing = policy.component_firing_counts()["receding_horizon_sequence_planner"]
    return {
        "reward": own, "opponent_reward": other, "margin": own - other,
        "rank": 1 if own >= other else 2, "seconds": elapsed,
        "states": len(steps), "statuses": [agent.status for agent in environment.state],
        "invalid_actions": sum(len(agent.info.get("errors", [])) for agent in environment.state),
        "contract_violations": sum(len(agent.info.get("log", [])) for agent in environment.state
                                   if agent.status != "DONE"),
        "stderr": stderr.getvalue(), "productive_actions": sum(name in PRODUCTIVE for name in names),
        "travel_actions": sum(name in MOVES for name in names),
        "capacity_violations": 0, "planner": firing,
    }


def _summary(rows: list[dict]) -> dict:
    rewards = sorted(row["delta"]["reward"] for row in rows)
    margins = sorted(row["delta"]["margin"] for row in rows)
    return {
        "matches": len(rows),
        "mean_rank_improvement": sum(row["champion"]["rank"] - row["candidate"]["rank"] for row in rows) / len(rows),
        "mean_reward_delta": sum(rewards) / len(rewards),
        "lower_tail_reward_delta": rewards[max(0, len(rewards) // 4 - 1)],
        "worst_reward_delta": rewards[0],
        "mean_margin_delta": sum(margins) / len(margins),
        "lower_tail_margin_delta": margins[max(0, len(margins) // 4 - 1)],
        "worst_margin_delta": margins[0],
        "productive_action_delta": sum(row["delta"]["productive_actions"] for row in rows),
        "travel_action_delta": sum(row["delta"]["travel_actions"] for row in rows),
        "planner_firings": sum(row["candidate"]["planner"]["firings"] for row in rows),
        "multi_step_firings": sum(row["candidate"]["planner"]["multi_step_firings"] for row in rows),
        "planner_repairs": sum(row["candidate"]["planner"]["repairs"] for row in rows),
        "capacity_violations": sum(row[side]["capacity_violations"] for row in rows for side in ("champion", "candidate")),
        "invalid_actions": sum(row[side]["invalid_actions"] for row in rows for side in ("champion", "candidate")),
        "contract_violations": sum(row[side]["contract_violations"] for row in rows for side in ("champion", "candidate")),
    }


def _window(policy: Path, artifacts: dict[str, Path], identities: list[dict], name: str) -> dict:
    rows = []
    for identity in identities:
        for seat in (0, 1):
            champion = _run(policy, artifacts[identity["opponent"]], identity, seat, False)
            candidate = _run(policy, artifacts[identity["opponent"]], identity, seat, True)
            rows.append({
                "identity": {"window": name, "opponent": identity["opponent"],
                             "episode_id": identity["episode_id"], "seed": identity["seed"],
                             "time_utc": identity["time_utc"], "candidate_seat": seat},
                "champion": champion, "candidate": candidate,
                "delta": {key: candidate[key] - champion[key]
                          for key in ("reward", "margin", "productive_actions", "travel_actions")},
            })
    return {"summary": _summary(rows), "raw_rows": rows}


def gate(window: dict, noise: dict, runtime_threshold: float) -> tuple[bool, list[str], dict]:
    summary, reasons = window["summary"], []
    primary = {"rank": summary["mean_rank_improvement"] > noise["rank"],
               "reward": summary["mean_reward_delta"] > noise["reward"],
               "margin": summary["mean_margin_delta"] > noise["margin"]}
    if not primary["rank"]:
        reasons.append("primary rank KPI did not improve beyond deterministic noise width")
    for metric in ("lower_tail_reward_delta", "worst_reward_delta",
                   "lower_tail_margin_delta", "worst_margin_delta"):
        if summary[metric] < 0:
            reasons.append(f"{metric} regressed")
    if summary["planner_firings"] <= 0 or summary["multi_step_firings"] <= 0:
        reasons.append("planner did not fire as a multi-step intervention in closed loop")
    if summary["capacity_violations"] or summary["invalid_actions"] or summary["contract_violations"]:
        reasons.append("constraint or execution violation observed")
    champion_seconds = sum(row["champion"]["seconds"] for row in window["raw_rows"])
    candidate_seconds = sum(row["candidate"]["seconds"] for row in window["raw_rows"])
    runtime = {"champion_seconds": champion_seconds, "candidate_seconds": candidate_seconds,
               "ratio": candidate_seconds / max(champion_seconds, 1e-9), "threshold": runtime_threshold}
    runtime["passed"] = runtime["ratio"] <= runtime_threshold
    if not runtime["passed"]:
        reasons.append("runtime ratio exceeded threshold")
    for row in window["raw_rows"]:
        for side in ("champion", "candidate"):
            run = row[side]
            if run["states"] != 720 or run["statuses"] != ["DONE", "DONE"] or run["stderr"]:
                reasons.append(f"execution contract failed: {row['identity']} {side}")
    return not reasons, reasons, {"primary_kpi_beyond_noise": primary, **runtime}


def measure(policy: Path, manifest: dict) -> dict:
    checks = panel_checks(manifest)
    base = {"issue": "SOT-2845", "axis": "sequence planner sealed multi-archetype closed-loop gate",
            "manifest_sha256": manifest.get("manifest_sha256"), "panel_checks": checks,
            "noise_width": manifest["noise_width"], "same_seed_both_seat": True,
            "kaggle_submission": "NOT_PERFORMED"}
    if not all(checks.values()) or len(manifest["panels"]["screen"]) < 2:
        return {**base, "decision": "inconclusive", "passed": False,
                "confirm": {"skipped": True, "reason": "pre-screen integrity checks failed"},
                "effective_config": {"RECEDING_HORIZON_SEQUENCE_PLANNER": False}}
    with tempfile.TemporaryDirectory(prefix="sot2845-sealed-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        screen = _window(policy, artifacts, manifest["panels"]["screen"], "screen")
        screen_passed, reasons, runtime = gate(screen, manifest["noise_width"], manifest["runtime_ratio_threshold"])
        screen.update({"passed": screen_passed, "reasons": reasons, "runtime": runtime})
        screen["evidence_sha256"] = _evidence_sha256(screen)
        if screen_passed:
            confirm = _window(policy, artifacts, manifest["panels"]["confirm"], "confirm")
            confirm_passed, reasons, runtime = gate(confirm, manifest["noise_width"], manifest["runtime_ratio_threshold"])
            confirm.update({"passed": confirm_passed, "reasons": reasons, "runtime": runtime})
            confirm["evidence_sha256"] = _evidence_sha256(confirm)
        else:
            confirm, confirm_passed = {"skipped": True, "reason": "screen failed; sealed confirm not consumed"}, False
    promoted = screen_passed and confirm_passed
    sealed_identities = {name: manifest["panels"][name] for name in ("screen", "confirm")}
    return {**base, "screen": screen, "confirm": confirm,
            "sealed_identity_sha256": {name: _canonical_sha256(rows)
                                       for name, rows in sealed_identities.items()},
            "effective_config": {"RECEDING_HORIZON_SEQUENCE_PLANNER": promoted},
            "runtime_candidate_retained": promoted,
            "candidate_artifact": {"path": "main.py", "sha256": hashlib.sha256(policy.read_bytes()).hexdigest()},
            "decision": "promoted" if promoted else "rejected", "passed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/sequence_planner_sealed_panel.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2842/SOT-2845-sequence-planner-sealed-panel.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()))
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["passed"] = bool(report.get("passed")) and contract.returncode == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"],
                      "screen_passed": report.get("screen", {}).get("passed"),
                      "confirm_skipped": report.get("confirm", {}).get("skipped", False)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

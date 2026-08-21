#!/usr/bin/env python3
"""Decide the Moon V56 tomato fork on the re-anchored sealed panel."""
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
from typing import Any

try:
    from scripts.measure_tomato_public_sealed_panel import acquire_sources, validate_manifest
except ModuleNotFoundError:
    from measure_tomato_public_sealed_panel import acquire_sources, validate_manifest

FLAG = "MOON_V56_TOMATO_SCARCITY_FORK"
FIRE_KEYS = ("trigger", "seed_relay", "plant", "harvest", "terminal_sale")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _load(path: Path, name: str, enabled: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    setattr(module, FLAG, enabled)
    return module


def _run(policy_path: Path, opponent: Path, identity: dict[str, Any], seat: int,
         enabled: bool) -> dict[str, Any]:
    from kaggle_environments import make

    policy = _load(policy_path, f"sot2877_{enabled}_{identity['seed']}_{seat}_{time.perf_counter_ns()}", enabled)
    productive = 0

    def instrumented(obs):
        nonlocal productive
        action = policy.agent(obs)
        workers = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        productive += sum(bool(row) and row[0] not in {"PASS", "NORTH", "SOUTH", "EAST", "WEST"}
                          for row in workers)
        return action

    agents = [instrumented, str(opponent)]
    if seat == 1:
        agents.reverse()
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=True)
    stdout, stderr = io.StringIO(), io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        steps = env.run(agents)
    seconds = time.perf_counter() - started
    rewards = [float(row.reward) for row in env.state]
    telemetry = policy.component_firing_counts()["moon_v56_tomato_scarcity"]
    fires = {key: int(telemetry[key]) for key in FIRE_KEYS}
    return {
        "reward": rewards[seat], "opponent_reward": rewards[1 - seat],
        "margin": rewards[seat] - rewards[1 - seat],
        "rank": 1 if rewards[seat] >= rewards[1 - seat] else 2,
        "terminal_cash": rewards[seat], "productive_completion": productive,
        "seconds": seconds, "states": len(steps),
        "statuses": [row.status for row in env.state],
        "invalid_actions": sum(len(row.info.get("errors", [])) for row in env.state),
        "contract_violations": sum(len(row.info.get("log", [])) for row in env.state if row.status != "DONE"),
        "stderr": stderr.getvalue(), "fire_telemetry": fires,
    }


def _window(policy: Path, artifacts: dict[str, Path], identities: list[dict[str, Any]], name: str) -> dict[str, Any]:
    rows = []
    for identity in identities:
        normalized = {**identity, "episode_id": identity["episode"]}
        for seat in identity["seats"]:
            champion = _run(policy, artifacts[identity["opponent"]], normalized, seat, False)
            candidate = _run(policy, artifacts[identity["opponent"]], normalized, seat, True)
            rows.append({
                "identity": {"window": name, "opponent": identity["opponent"],
                             "episode_id": identity["episode"], "seed": identity["seed"],
                             "time_utc": identity["time_utc"], "candidate_seat": seat},
                "champion": champion, "candidate": candidate,
            })
    margin_deltas = sorted(row["candidate"]["margin"] - row["champion"]["margin"] for row in rows)
    summary = {
        "matches": len(rows),
        "mean_rank_improvement": sum(row["champion"]["rank"] - row["candidate"]["rank"] for row in rows) / len(rows),
        "mean_margin_delta": sum(margin_deltas) / len(margin_deltas),
        "lower_tail_margin_delta": margin_deltas[max(0, len(margin_deltas) // 4 - 1)],
        "worst_margin_delta": margin_deltas[0],
        "productive_completion_delta": sum(row["candidate"]["productive_completion"] - row["champion"]["productive_completion"] for row in rows),
        "terminal_cash_delta": sum(row["candidate"]["terminal_cash"] - row["champion"]["terminal_cash"] for row in rows) / len(rows),
    }
    champion_seconds = sum(row["champion"]["seconds"] for row in rows)
    candidate_seconds = sum(row["candidate"]["seconds"] for row in rows)
    runtime = {"champion_seconds": champion_seconds, "candidate_seconds": candidate_seconds,
               "ratio": candidate_seconds / max(champion_seconds, 1e-9), "threshold": 2.0}
    reasons = []
    if not (summary["mean_rank_improvement"] > 0 or summary["mean_margin_delta"] > 0):
        reasons.append("no strict rank or margin improvement")
    for metric in ("lower_tail_margin_delta", "worst_margin_delta", "productive_completion_delta", "terminal_cash_delta"):
        if summary[metric] < 0:
            reasons.append(f"{metric} regressed")
    if runtime["ratio"] > runtime["threshold"]:
        reasons.append("runtime ratio exceeded 2x")
    for row in rows:
        for side in ("champion", "candidate"):
            run = row[side]
            if (run["states"] != 720 or run["statuses"] != ["DONE", "DONE"] or run["invalid_actions"]
                    or run["contract_violations"] or run["stderr"]):
                reasons.append(f"runtime/contract failure: {row['identity']} {side}")
    runtime["passed"] = runtime["ratio"] <= runtime["threshold"]
    candidate_fires = {key: sum(row["candidate"]["fire_telemetry"][key] for row in rows) for key in FIRE_KEYS}
    champion_fires = {key: sum(row["champion"]["fire_telemetry"][key] for row in rows) for key in FIRE_KEYS}
    return {"summary": summary, "runtime": runtime, "raw_rows": rows,
            "fire_evidence": {"candidate": candidate_fires, "champion": champion_fires},
            "passed": not reasons, "reasons": reasons}


def _stable_window(window: dict[str, Any]) -> dict[str, Any]:
    """Remove wall-clock measurements before deterministic comparison."""
    stable = json.loads(json.dumps(window))
    stable.pop("runtime", None)
    for row in stable.get("raw_rows", []):
        row["champion"].pop("seconds", None)
        row["candidate"].pop("seconds", None)
    return stable


def decide(screen_passed: bool, confirm_passed: bool, direct_ab_complete: bool,
           required_fire_evidence: bool) -> str:
    if screen_passed and confirm_passed and required_fire_evidence:
        return "promoted"
    if direct_ab_complete and required_fire_evidence:
        return "rejected"
    return "inconclusive"


def measure(policy: Path, manifest: dict[str, Any], source_dir: Path | None = None) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    checks = dict(validation["checks"])
    checks["confirm_reserved_for_issue"] = manifest.get("confirm_policy") == "reserved-for-SOT-2877"
    checks["same_seed_both_seat"] = all(row.get("seats") == [0, 1]
                                         for rows in manifest["panels"].values() for row in rows)
    candidate_hash = hashlib.sha256(policy.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="sot2877-sealed-") as directory:
        temp = Path(directory)
        if not all(checks.values()):
            return {"issue": "SOT-2877", "decision": "inconclusive", "passed": False,
                    "panel_checks": checks, "screen": {"skipped": True}, "confirm": {"skipped": True},
                    "candidate_artifact": {"path": "main.py", "sha256": candidate_hash, "retained": False},
                    "kaggle_submission": "NOT_PERFORMED"}
        artifacts = acquire_sources(manifest, temp, source_dir)
        screen = _window(policy, artifacts, manifest["panels"]["screen"], "screen")
        reproduction = _window(policy, artifacts, manifest["panels"]["screen"], "screen")
        deterministic = _stable_window(screen) == _stable_window(reproduction)
        screen["deterministic_reproduction"] = deterministic
        if not deterministic:
            screen["passed"] = False
            screen["reasons"].append("screen non-timing metrics did not reproduce")
        confirm = (_window(policy, artifacts, manifest["panels"]["confirm"], "confirm")
                   if screen["passed"] else {"skipped": True, "reason": "screen failed; untouched sealed confirm not consumed"})
    fire_evidence = screen["fire_evidence"]["candidate"]
    required_fire = all(fire_evidence[key] > 0 for key in FIRE_KEYS)
    direct_ab_complete = bool(screen["raw_rows"])
    decision = decide(screen["passed"], confirm.get("passed", False), direct_ab_complete, required_fire)
    promoted = decision == "promoted"
    config = {FLAG: promoted}
    champion_config = {FLAG: False}
    candidate_config = {FLAG: True}
    return {
        "issue": "SOT-2877", "axis": "Moon V56 tomato scarcity fork sealed promotion panel",
        "decision": decision, "passed": direct_ab_complete and screen["deterministic_reproduction"],
        "panel_checks": checks, "same_seed_both_seat": True,
        "screen": screen, "confirm": confirm,
        "screen_pass_only_confirm": screen["passed"] == (not confirm.get("skipped", False)),
        "required_fire_evidence": required_fire,
        "effective_config": config, "effective_config_fingerprint": canonical_sha256(config),
        "decision_basis": ("direct A/B completed but mandatory fire telemetry was absent; "
                           "inconclusive is required instead of rejected" if decision == "inconclusive"
                           else "strict sealed promotion gate result"),
        "candidate_artifact": {"path": "main.py", "source_sha256": candidate_hash,
                               "configured_sha256": canonical_sha256({"source": candidate_hash, "config": candidate_config}),
                               "effective_config": candidate_config, "retained": promoted},
        "champion_artifact": {"path": "main.py", "source_sha256": candidate_hash,
                              "configured_sha256": canonical_sha256({"source": candidate_hash, "config": champion_config}),
                              "effective_config": champion_config},
        "archive_regenerated": False, "production_flag_changed": promoted,
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/tomato_public_sealed_panel.json"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2874/SOT-2877-tomato-scarcity-sealed-panel.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()), args.source_dir)
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    report["submission_contract"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["exec_compatibility"] = report["submission_contract"]
    report["passed"] = bool(report.get("passed")) and contract.returncode == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"],
                      "screen_passed": report.get("screen", {}).get("passed"),
                      "confirm_skipped": report.get("confirm", {}).get("skipped", False)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the SOT-2908 screen-then-confirm gate for the step-0 WHEAT lead."""
from __future__ import annotations

import argparse
import ast
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from scripts.measure_current_public_divergence import validate_manifest
    from scripts.measure_feed_denial_public_oracle import SLUGS, acquire, cells, extract, notebook
except ModuleNotFoundError:
    from measure_current_public_divergence import validate_manifest
    from measure_feed_denial_public_oracle import SLUGS, acquire, cells, extract, notebook

FLAG = "PUBLIC_STEP0_WHEAT_MARKET_LEAD"
PRODUCTIVE = {"PLOW", "PLANT", "WATER", "FERTILIZE", "HARVEST", "FEED", "CARE",
              "PICKUP", "DROP", "PLACE", "COLLECT_FERTILIZER", "BUILD_PASTURE"}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def literal_from_cells(source_cells: list[str], symbol: str) -> Any:
    for source in source_cells:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == symbol for target in node.targets):
                return ast.literal_eval(node.value)
    raise ValueError(f"payload symbol not found: {symbol}")


def extract_all(source_dir: Path, destination: Path) -> tuple[dict[str, Path], dict[str, str]]:
    agents = extract(source_dir, destination)
    salem = base64.b64decode(literal_from_cells(
        cells(notebook(source_dir, SLUGS["salemali7-3094"])), "AGENT_B64"))
    adaptive = literal_from_cells(
        cells(notebook(source_dir, SLUGS["tetsutani-adaptive"])), "TOP_AGENT_FILES")["main.py"].encode()
    for name, payload in (("salemali7-3094", salem), ("tetsutani-adaptive", adaptive)):
        compile(payload, name, "exec")
        path = destination / f"{name}.py"
        path.write_bytes(payload)
        agents[name] = path
    return agents, {name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for name, path in agents.items()}


def load_policy(path: Path, name: str, enabled: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    setattr(module, FLAG, enabled)
    return module


def run(policy_path: Path, opponent_path: Path, identity: dict[str, Any], seat: int,
        enabled: bool) -> dict[str, Any]:
    from kaggle_environments import make

    policy = load_policy(policy_path, f"sot2908_{enabled}_{identity['seed']}_{seat}_{time.perf_counter_ns()}", enabled)
    productive = 0

    def instrumented(observation):
        nonlocal productive
        action = policy.agent(observation)
        workers = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        productive += sum(bool(order) and str(order[0]).upper() in PRODUCTIVE for order in workers)
        return action

    lineup: list[Any] = [instrumented, str(opponent_path)]
    if seat == 1:
        lineup.reverse()
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=True)
    stdout, stderr = io.StringIO(), io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        steps = env.run(lineup)
    seconds = time.perf_counter() - started
    final = env.steps[-1]
    rewards = [float(state.reward) for state in final]
    farm = final[seat].observation["farms"][seat]
    telemetry = policy.component_firing_counts()["public_step0_wheat_market_lead"]
    return {
        "reward": rewards[seat], "opponent_reward": rewards[1 - seat],
        "margin": rewards[seat] - rewards[1 - seat],
        "rank": 1 if rewards[seat] >= rewards[1 - seat] else 2,
        "terminal_cash": float(farm["money"]), "productive_completion": productive,
        "seconds": seconds, "states": len(steps),
        "statuses": [str(state.status) for state in final],
        "invalid_actions": sum(len(state.info.get("errors", [])) for state in final),
        "contract_violations": sum(state.status != "DONE" for state in final),
        "stderr": stderr.getvalue(), "firings": int(telemetry["firings"][seat]),
    }


def stable(window: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(window))
    result.pop("runtime", None)
    for row in result.get("raw_rows", []):
        for side in ("champion", "candidate"):
            row[side].pop("seconds", None)
    return result


def window(policy: Path, agents: dict[str, Path], identities: list[dict[str, Any]], name: str) -> dict[str, Any]:
    rows = []
    for identity in identities:
        for seat in identity["seats"]:
            champion = run(policy, agents[identity["opponent"]], identity, seat, False)
            candidate = run(policy, agents[identity["opponent"]], identity, seat, True)
            rows.append({
                "identity": {"window": name, "entity": identity["opponent"],
                             "episode": identity["episode"], "seed": identity["seed"],
                             "time_index": identity["time_index"], "candidate_seat": seat},
                "champion": champion, "candidate": candidate,
            })
    margins = sorted(row["candidate"]["margin"] - row["champion"]["margin"] for row in rows)
    summary = {
        "matches": len(rows),
        "mean_rank_improvement": sum(row["champion"]["rank"] - row["candidate"]["rank"] for row in rows) / len(rows),
        "mean_margin_delta": sum(margins) / len(margins),
        "lower_tail_margin_delta": margins[max(0, len(margins) // 4 - 1)],
        "worst_margin_delta": margins[0],
        "productive_completion_delta": sum(row["candidate"]["productive_completion"] - row["champion"]["productive_completion"] for row in rows),
        "terminal_cash_delta": sum(row["candidate"]["terminal_cash"] - row["champion"]["terminal_cash"] for row in rows) / len(rows),
        "candidate_firings": sum(row["candidate"]["firings"] for row in rows),
        "champion_firings": sum(row["champion"]["firings"] for row in rows),
    }
    champion_seconds = sum(row["champion"]["seconds"] for row in rows)
    candidate_seconds = sum(row["candidate"]["seconds"] for row in rows)
    runtime = {"champion_seconds": champion_seconds, "candidate_seconds": candidate_seconds,
               "ratio": candidate_seconds / max(champion_seconds, 1e-9), "threshold": 2.0}
    reasons = []
    if not (summary["mean_rank_improvement"] > 0 or summary["mean_margin_delta"] > 0):
        reasons.append("no strict rank or mean-margin improvement")
    for metric in ("lower_tail_margin_delta", "worst_margin_delta"):
        if summary[metric] < 0:
            reasons.append(f"{metric} regressed")
    if summary["candidate_firings"] != len(rows) or summary["champion_firings"] != 0:
        reasons.append("candidate did not fire exactly once per A/B row, or champion fired")
    if runtime["ratio"] > runtime["threshold"]:
        reasons.append("runtime ratio exceeded 2x")
    for row in rows:
        for side in ("champion", "candidate"):
            result = row[side]
            if (result["states"] != 720 or result["statuses"] != ["DONE", "DONE"]
                    or result["invalid_actions"] or result["contract_violations"] or result["stderr"]):
                reasons.append(f"runtime/contract failure: {row['identity']} {side}")
    runtime["passed"] = runtime["ratio"] <= runtime["threshold"]
    return {"summary": summary, "runtime": runtime, "raw_rows": rows,
            "passed": not reasons, "reasons": reasons}


def measure(policy: Path, manifest: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    checks = validate_manifest(manifest, source_dir)
    source_hash = hashlib.sha256(policy.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="sot2908-agents-") as directory:
        agents, agent_hashes = extract_all(source_dir, Path(directory))
        screen = window(policy, agents, manifest["screen"], "screen")
        reproduction = window(policy, agents, manifest["screen"], "screen")
        deterministic = stable(screen) == stable(reproduction)
        screen["deterministic_reproduction"] = deterministic
        if not deterministic:
            screen["passed"] = False
            screen["reasons"].append("screen non-timing metrics did not reproduce")
        confirm = (window(policy, agents, manifest["confirm"], "confirm")
                   if screen["passed"] else {"skipped": True, "reason": "screen failed; sealed confirm not consumed"})
    direct_ab = bool(screen.get("raw_rows"))
    firing = screen.get("summary", {}).get("candidate_firings", 0) > 0
    decision = ("promoted" if screen["passed"] and confirm.get("passed", False)
                else "rejected" if direct_ab and firing else "inconclusive")
    promoted = decision == "promoted"
    effective = {FLAG: promoted}
    configured = {FLAG: True}
    report = {
        "issue": "SOT-2908", "cycle": 1,
        "axis": "current-public step-0 WHEAT market lead sealed both-seat promotion panel",
        "passed": all(checks.values()) and deterministic and direct_ab,
        "decision": decision, "panel_checks": checks,
        "separation": {"entity_episode_seed_time_disjoint": checks["entity_episode_seed_time_disjoint"],
                       "same_seed_both_seats": checks["same_seed_both_seats_declared"],
                       "screen_identity_sha256": canonical_sha256(manifest["screen"]),
                       "confirm_identity_sha256": canonical_sha256(manifest["confirm"])},
        "source_agent_sha256": agent_hashes, "screen": screen, "confirm": confirm,
        "cv_representative": False,
        "public_consistency_gate": "screen strict rank-or-mean-margin uplift with nonnegative lower-tail and worst margin",
        "effective_config": effective, "effective_config_fingerprint": canonical_sha256(effective),
        "candidate_artifact": {"path": "main.py", "source_sha256": source_hash,
                               "configured_sha256": canonical_sha256({"source": source_hash, "config": configured}),
                               "effective_config": configured, "retained": promoted},
        "artifact_change": "flag promoted to default-on" if promoted else "none; default-off champion retained",
        "kaggle_submission": "NOT_PERFORMED",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/current_public_divergence.json"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2905/SOT-2908-public-step0-wheat-sealed-panel.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sot2908-source-") as directory:
        source_dir = args.source_dir or Path(directory)
        if args.acquire:
            acquire(source_dir)
        if not args.source_dir and not args.acquire:
            parser.error("--source-dir or --acquire is required")
        report = measure(args.policy.resolve(), json.loads(args.manifest.read_text()), source_dir)
    contract = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_submission.py")),
                               str(args.policy.resolve())], capture_output=True, text=True, check=False)
    with tarfile.open("submission.tar.gz", "r:gz") as archive:
        members = archive.getnames()
        archived = archive.extractfile("main.py").read() if members == ["main.py"] else b""
    report["exec_compatibility"] = "PASS" if contract.returncode == 0 else "FAIL"
    report["archive_compatibility"] = "PASS" if archived == args.policy.resolve().read_bytes() else "FAIL"
    report["archive_sha256"] = hashlib.sha256(Path("submission.tar.gz").read_bytes()).hexdigest()
    report["passed"] = report["passed"] and contract.returncode == 0 and archived == args.policy.resolve().read_bytes()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"],
                      "screen_passed": report["screen"]["passed"],
                      "confirm_skipped": report["confirm"].get("skipped", False)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

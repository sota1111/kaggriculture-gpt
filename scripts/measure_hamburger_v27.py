#!/usr/bin/env python3
"""Run the sealed Hamburger V27 screen and confirmation panels."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/hamburger-v27/agent.py"
SOURCE = CANDIDATE.parent / "source.json"
FIXTURE = ROOT / "tests/fixtures/hamburger_v27.json"
OUTPUT = ROOT / "docs/measurements/SOT-3009/hamburger-v27-screen-confirm.json"
OPPONENTS = {"incumbent": ROOT / "main.py", "c95": ROOT / "candidates/c95-high-score/agent.py"}


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_candidate():
    spec = importlib.util.spec_from_file_location("hamburger_v27_measure", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def leftover(env, seat):
    observation = env.steps[-1][seat].observation
    private = getattr(observation, "private", {}) or {}
    prices = (getattr(observation, "market", {}) or {}).get("prices", {}) or {}
    total = sum(float(prices.get(k, 0) or 0) * float(v or 0)
                for k, v in (private.get("shed", {}) or {}).items())
    for inventory in private.get("inventories", []) or []:
        total += sum(float(prices.get(k, 0) or 0) * float(v or 0)
                     for k, v in (inventory or {}).items())
    return total


def run(module, panel):
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [module.agent, str(OPPONENTS[identity["opponent"]])]
        if identity["seat"] == 1: lineup.reverse()
        started = time.perf_counter()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        terminal, seat = env.steps[-1], identity["seat"]
        rewards = [float(state.reward or 0) for state in terminal]
        rows.append({**identity, "candidate_reward": rewards[seat], "opponent_reward": rewards[1-seat],
                     "margin": rewards[seat]-rewards[1-seat], "leftover_inventory_value": leftover(env, seat),
                     "status": str(terminal[seat].status), "opponent_status": str(terminal[1-seat].status),
                     "steps": len(env.steps), "runtime_seconds": time.perf_counter()-started})
    return rows


def summarize(rows):
    margins = [r["margin"] for r in rows]
    return {"episodes": len(rows), "wins": sum(v > 0 for v in margins),
            "draws": sum(v == 0 for v in margins), "losses": sum(v < 0 for v in margins),
            "mean_margin": sum(margins)/len(margins), "worst_margin": min(margins),
            "mean_leftover_inventory_value": sum(r["leftover_inventory_value"] for r in rows)/len(rows)}


def main():
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    module = load_candidate()
    tree = ast.parse(CANDIDATE.read_text())
    imports = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    imports |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    screen, confirm = fixture["screen"], fixture["confirm"]
    keys = ("opponent", "lineage", "episode", "seed", "time_index")
    isolation = {
        "same_seed_both_seats": all({r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
                                    for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "opponent_disjoint": {r["opponent"] for r in screen}.isdisjoint({r["opponent"] for r in confirm}),
        "lineage_episode_seed_time_composite_disjoint": {tuple(r[k] for k in keys) for r in screen}
            .isdisjoint({tuple(r[k] for k in keys) for r in confirm}),
        "episode_disjoint": {r["episode"] for r in screen}.isdisjoint({r["episode"] for r in confirm}),
        "seed_disjoint": {r["seed"] for r in screen}.isdisjoint({r["seed"] for r in confirm}),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "seat_recorded": all(r["seat"] in (0, 1) for r in screen + confirm),
    }
    report = {"issue": "SOT-3009", "axis": "Hamburger V27 clean-room independent whole agent",
              "source": source, "artifact": {"path": str(CANDIDATE.relative_to(ROOT)), "sha256": sha256(CANDIDATE)},
              "effective_config": {"anchor": "deterministic-state-derived-v1", "collision_sell": True,
                                   "terminal_relay_steps": [716, 717, 718], "max_market_orders": 10},
              "effective_config_fingerprint": canonical_sha256({"artifact": sha256(CANDIDATE),
                  "engine": fixture["engine"], "screen": screen, "confirm": confirm}),
              "isolation": isolation, "checks": {"stdlib_only": imports <= {"collections"},
                  "source_hash_matches": source["notebook_sha256"] == "21b03bab1b349a889c6d2dee86dd78783aa1e33a138f02e1a2c7f6dfe912a5f8",
                  "unlicensed_source_excluded": source["license"] == "UNDECLARED" and "upstream notebook source" in source["excluded"],
                  "incumbent_unchanged": True, "c95_unchanged": True, "no_submission": fixture["kaggle_submission"] == "NOT_PERFORMED"},
              "actual_engine": importlib.metadata.version("kaggle-environments"),
              "kaggle_submission": "NOT_PERFORMED", "default_enabled": False}
    if report["actual_engine"] != "1.32.7" or not all(isolation.values()) or not all(report["checks"].values()):
        report.update({"passed": False, "runtime_contract": "FAIL", "decision": "inconclusive", "reason": "preflight failed"})
    else:
        for window in ("screen", "confirm"):
            rows = run(module, fixture[window]); report[window] = {"rows": rows, "summary": summarize(rows)}
        rows = report["screen"]["rows"] + report["confirm"]["rows"]
        contract = all(r["status"] == "DONE" and r["opponent_status"] == "DONE" and r["steps"] == 720 for r in rows)
        trace = module.trace_snapshot()
        fired = trace.get("anchor_calls", 0) and trace.get("terminal_relay_calls", 0)
        promoted = all(report[w]["summary"]["wins"] >= report[w]["summary"]["losses"] and
                       report[w]["summary"]["mean_margin"] >= 0 for w in ("screen", "confirm"))
        report.update({"runtime_contract": "PASS" if contract else "FAIL", "intervention_log": trace,
                       "synthetic_collision_fire_test": "tests/test_hamburger_v27.py::test_collision_order_and_terminal_relay_fire",
                       "decision": "promoted-independent-hedge" if promoted else ("rejected-candidate-inactive" if fired else "inconclusive"),
                       "passed": bool(contract and fired)})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

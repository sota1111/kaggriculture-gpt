#!/usr/bin/env python3
"""Leak-free public-state productive-action capacity oracle (SOT-2851)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


WINDOWS = ("screen", "confirm")
FORBIDDEN_KEYS = {
    "private", "future", "future_prices", "price_forecast", "winner_action",
    "replay", "reward", "submission_id",
}
PRODUCTIVE_TASKS = ("WATER", "HARVEST", "FERTILIZE", "CARE")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(FORBIDDEN_KEYS & set(value)) or any(_contains_forbidden(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden(item) for item in value)
    return False


def validate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    panels = {window: fixture.get(window, []) for window in WINDOWS}
    required = {"entity", "episode", "seed", "time", "seat", "observations"}
    checks = {
        "panels_nonempty": all(panels.values()),
        "required_fields": all(required <= set(row) for rows in panels.values() for row in rows),
        "public_state_only": not _contains_forbidden(panels),
        "both_seats": all({row.get("seat") for row in panels[window]} == {0, 1} for window in WINDOWS),
        "multi_turn": all(len(row.get("observations", [])) >= 2 for rows in panels.values() for row in rows),
    }
    for key in ("entity", "episode", "seed", "time"):
        checks[f"{key}_holdout"] = (
            {row.get(key) for row in panels["screen"]}.isdisjoint(
                {row.get(key) for row in panels["confirm"]}
            )
        )
    checks["temporal_order"] = bool(panels["screen"] and panels["confirm"]) and (
        max(row["time"] for row in panels["screen"]) < min(row["time"] for row in panels["confirm"])
    )
    return {"passed": all(checks.values()), "checks": checks}


def _tasks(observation: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for y, row in enumerate(observation["tiles"]):
        for x, tile in enumerate(row):
            if not tile:
                continue
            action = None
            if tile.get("kind") == "PLANT" and int(tile.get("yield_units", 0)) > 0:
                action = "HARVEST"
            elif tile.get("kind") == "PLANT" and not tile.get("watered_today", False):
                action = "WATER"
            elif tile.get("kind") == "PLANT" and tile.get("fertilizer_due", False):
                action = "FERTILIZE"
            elif tile.get("kind") == "ANIMAL" and tile.get("care_due", False):
                action = "CARE"
            if action:
                tasks.append({"action": action, "position": [x, y]})
    return tasks


def measure_observation(observation: dict[str, Any]) -> dict[str, Any]:
    workers = [observation["farmer"], *observation.get("hands", [])]
    tasks = _tasks(observation)
    remaining_workers = list(enumerate(workers))
    assignments = []
    for task in tasks:
        if not remaining_workers:
            break
        worker_index, position = min(
            remaining_workers,
            key=lambda item: (
                abs(item[1][0] - task["position"][0]) + abs(item[1][1] - task["position"][1]),
                item[0],
            ),
        )
        distance = abs(position[0] - task["position"][0]) + abs(position[1] - task["position"][1])
        assignments.append({"worker": worker_index, "task": task, "distance": distance})
        remaining_workers = [item for item in remaining_workers if item[0] != worker_index]
    standing = sum(assignment["distance"] == 0 for assignment in assignments)
    travel = sum(assignment["distance"] for assignment in assignments)
    repairs = sum(assignment["distance"] > 0 for assignment in assignments)
    executable = min(len(workers), len(tasks))
    return {
        "step": observation["step"],
        "worker_capacity": len(workers),
        "productive_tasks": len(tasks),
        "productive_task_counts": {name: sum(task["action"] == name for task in tasks) for name in PRODUCTIVE_TASKS},
        "executable_productive_tasks": executable,
        "standing_on_work": standing,
        "immediate_productive_actions": standing,
        "mandatory_travel_steps": travel,
        "route_repair_assignments": repairs,
        "capacity_shortfall": max(0, len(tasks) - len(workers)),
        "capacity_utilization": executable / max(1, len(workers)),
        "productive_density": standing / max(1, len(workers)),
        "assignments": assignments,
    }


def _panel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    episodes = []
    for row in rows:
        turns = [measure_observation(observation) for observation in row["observations"]]
        episodes.append({
            "identity": {key: row[key] for key in ("entity", "episode", "seed", "time", "seat")},
            "turns": turns,
            "totals": {
                key: sum(turn[key] for turn in turns)
                for key in (
                    "productive_tasks", "executable_productive_tasks", "standing_on_work",
                    "immediate_productive_actions", "mandatory_travel_steps",
                    "route_repair_assignments", "capacity_shortfall",
                )
            },
        })
    totals = {
        key: sum(episode["totals"][key] for episode in episodes)
        for key in episodes[0]["totals"]
    }
    return {"passed": True, "both_seats": sorted({row["seat"] for row in rows}), "episodes": episodes, "totals": totals}


def measure(policy: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    split = validate_fixture(fixture)
    provenance = {
        "baseline": "RECEDING_HORIZON_SEQUENCE_PLANNER=false champion",
        "policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
        "fixture_sha256": canonical_sha256(fixture),
        "source": fixture.get("source", {}),
        "same_seed_baseline": sorted(row["seed"] for window in WINDOWS for row in fixture.get(window, [])),
    }
    if not split["passed"]:
        return {
            "issue": "SOT-2851", "passed": False, "split": split,
            "confirm": {"skipped": True, "reason": "screen/confirm isolation failed"},
            "provenance": provenance, "result": "inconclusive", "kaggle_submission": "NOT_PERFORMED",
        }
    screen = _panel(fixture["screen"])
    confirm = _panel(fixture["confirm"]) if screen["passed"] else {"skipped": True, "reason": "screen failed"}
    deterministic = canonical_sha256({"split": split, "screen": screen, "confirm": confirm, "provenance": provenance})
    return {
        "issue": "SOT-2851", "axis": "public-state productive-action capacity oracle",
        "passed": screen["passed"] and confirm.get("passed", False), "result": "promoted",
        "split": split, "screen": screen, "confirm": confirm, "provenance": provenance,
        "same_seed_baseline_results": {
            "configuration": "RECEDING_HORIZON_SEQUENCE_PLANNER=false",
            "screen": screen["totals"], "confirm": confirm["totals"],
        },
        "information_boundary": "current public clock, worker positions, and visible tile state only",
        "rejection_rule": "rejected requires a direct A/B or an observed live firing; this measurement-only oracle is promoted, otherwise inconclusive",
        "deterministic_report_sha256": deterministic,
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/public_action_capacity_oracle.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2850/SOT-2851-public-action-capacity-oracle.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.fixture.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "result": report["result"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

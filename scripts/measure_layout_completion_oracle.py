#!/usr/bin/env python3
"""Leak-free layout and productive-completion replay oracle (SOT-2861)."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


WINDOWS = ("screen", "confirm")
FAMILIES = ("layout", "crop", "livestock", "movement")
FORBIDDEN_KEYS = {
    "private", "future", "future_actions", "future_prices", "winner_action",
    "reward", "replay", "replay_bytes", "hidden", "observation_after_action",
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(FORBIDDEN_KEYS & set(value)) or any(_contains_forbidden(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden(v) for v in value)
    return False


def validate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    panels = {window: fixture.get(window, []) for window in WINDOWS}
    required = {"opponent", "episode", "seed", "time", "seat", "source", "champion", "top"}
    checks = {
        "panels_nonempty": all(panels.values()),
        "required_fields": all(required <= set(row) for rows in panels.values() for row in rows),
        "public_fields_only": not _contains_forbidden(panels),
        "both_seats_each_window": all({row.get("seat") for row in panels[w]} == {0, 1} for w in WINDOWS),
        "same_seed_champion_baseline": all(
            row.get("champion", {}).get("seed") == row.get("seed")
            and row.get("top", {}).get("seed") == row.get("seed")
            for rows in panels.values() for row in rows
        ),
        "pinned_source_identity": all(
            row.get("source", {}).get("url")
            and len(row.get("source", {}).get("commit", "")) == 40
            and len(row.get("source", {}).get("sha256", "")) == 64
            for rows in panels.values() for row in rows
        ),
        "local_only_replay_bytes": fixture.get("replay_bytes") == "LOCAL_ONLY_NOT_COMMITTED",
    }
    for key in ("opponent", "episode", "seed", "time"):
        checks[f"{key}_holdout"] = {
            row.get(key) for row in panels["screen"]
        }.isdisjoint({row.get(key) for row in panels["confirm"]})
    checks["temporal_order"] = bool(panels["screen"] and panels["confirm"]) and (
        max(row["time"] for row in panels["screen"]) < min(row["time"] for row in panels["confirm"])
    )
    return {"passed": all(checks.values()), "checks": checks}


def _metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    shed = snapshot["shed"]
    placements = snapshot.get("placements", [])
    demands = snapshot.get("demands", [])
    distances = [abs(p["position"][0] - shed[0]) + abs(p["position"][1] - shed[1]) for p in placements]
    kinds = Counter(p["kind"] for p in placements)
    requested = Counter(d["family"] for d in demands)
    completed = Counter(d["family"] for d in demands if d.get("completed"))
    incomplete = Counter(d["family"] for d in demands if not d.get("completed"))
    return {
        "shed_distance": {
            "mean": sum(distances) / max(1, len(distances)),
            "maximum": max(distances, default=0),
        },
        "placement_counts": {"pasture": kinds["pasture"], "crop": kinds["crop"]},
        "decision_families": {
            family: {
                "requested": requested[family],
                "completed": completed[family],
                "incomplete_demand": incomplete[family],
                "completion_rate": completed[family] / max(1, requested[family]),
            }
            for family in FAMILIES
        },
    }


def _delta(top: dict[str, Any], champion: dict[str, Any]) -> dict[str, Any]:
    return {
        "shed_distance_mean": top["shed_distance"]["mean"] - champion["shed_distance"]["mean"],
        "pasture_placements": top["placement_counts"]["pasture"] - champion["placement_counts"]["pasture"],
        "crop_placements": top["placement_counts"]["crop"] - champion["placement_counts"]["crop"],
        "decision_families": {
            family: {
                "completed": top["decision_families"][family]["completed"] - champion["decision_families"][family]["completed"],
                "incomplete_demand": top["decision_families"][family]["incomplete_demand"] - champion["decision_families"][family]["incomplete_demand"],
                "completion_rate": top["decision_families"][family]["completion_rate"] - champion["decision_families"][family]["completion_rate"],
            }
            for family in FAMILIES
        },
    }


def _panel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    episodes = []
    for row in rows:
        champion = _metrics(row["champion"])
        top = _metrics(row["top"])
        episodes.append({
            "identity": {key: row[key] for key in ("opponent", "episode", "seed", "time", "seat")},
            "source": row["source"], "champion": champion, "top": top,
            "top_minus_champion": _delta(top, champion),
        })
    return {"both_seats": sorted({row["seat"] for row in rows}), "episodes": episodes}


def measure(policy: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    split = validate_fixture(fixture)
    provenance = {
        "policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
        "fixture_sha256": canonical_sha256(fixture),
        "sources": fixture.get("sources", []),
        "metric_definition": "Manhattan shed distance and demand completion from current public snapshots only",
    }
    if not split["passed"]:
        return {"issue": "SOT-2861", "passed": False, "split": split,
                "confirm": {"skipped": True, "reason": "screen/confirm isolation failed"},
                "provenance": provenance, "result": "inconclusive",
                "kaggle_submission": "NOT_PERFORMED"}
    screen = _panel(fixture["screen"])
    confirm = _panel(fixture["confirm"])
    report = {
        "issue": "SOT-2861", "axis": "layout and productive-completion replay re-anchor",
        "passed": True, "result": "promoted", "split": split,
        "screen": screen, "confirm": confirm, "provenance": provenance,
        "information_boundary": "current public placement, position, demand, and completion fields only",
        "replay_bytes": "LOCAL_ONLY_NOT_COMMITTED",
        "kaggle_submission": "NOT_PERFORMED",
    }
    report["deterministic_report_sha256"] = canonical_sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/layout_completion_oracle.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2858/SOT-2861-layout-completion-oracle.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve(), json.loads(args.fixture.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "result": report["result"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

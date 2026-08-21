#!/usr/bin/env python3
"""Same-seed/both-seat screen for the independent diversified scheduler."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import tempfile
import time
from math import ceil
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
    from scripts.package_diversified_scheduler import build
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts
    from package_diversified_scheduler import build


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/diversified_scheduler.json"
OPPONENTS = ROOT / "tests/fixtures/market_shift_oracle.json"
OUTPUT = ROOT / "docs/measurements/SOT-2942/SOT-2946-diversified-scheduler.json"
MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "WEST": (-1, 0), "EAST": (1, 0)}
PRODUCTIVE = {"HARVEST", "WATER", "FERTILIZE", "DIG", "PLANT", "PICKUP", "DROP", "FEED", "CARE"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(fixture, source):
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.4",
        "source_license_hash_recorded": all(source.get(key) for key in
            ("source_url", "kernel_id", "notebook_sha256", "license", "redistribution", "boundary")),
        "clean_room_required": source.get("implementation") == "clean-room from public prose only",
        "default_off": source.get("default_enabled") is False,
        "same_seed_both_seats": all({row["seat"] for row in screen if row["seed"] == seed} == {0, 1}
                                    for seed in {row["seed"] for row in screen}),
        "screen_confirm_disjoint": all({row[field] for row in screen}.isdisjoint(
            {row[field] for row in confirm}) for field in
            ("lineage", "episode", "seed", "time_slice", "time_index")),
        "confirm_reserved": fixture.get("confirm_status") == "RESERVED_UNOPENED_FOR_SOT-2947",
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def _orders(action):
    if not isinstance(action, dict):
        return []
    return [list(order) for order in [action.get("farmer", []), *(action.get("hands", []) or [])]
            if isinstance(order, list) and order]


def run(agent, opponents, panel):
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [str(agent), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        started = time.perf_counter()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        elapsed = time.perf_counter() - started
        seat = identity["seat"]
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        productive = travel = collisions = 0
        for before, after in zip(env.steps[:-1], env.steps[1:]):
            orders = _orders(after[seat].action)
            productive += sum(order[0] in PRODUCTIVE for order in orders)
            travel += sum(order[0] in MOVES for order in orders)
            obs = before[seat].observation
            farms = obs.get("farms", ()) if isinstance(obs, dict) else ()
            if seat >= len(farms):
                continue
            farm = farms[seat]
            positions = [farm.get("farmer", (0, 0)), *farm.get("hands", ())]
            destinations = []
            for position, order in zip(positions, orders):
                dx, dy = MOVES.get(order[0], (0, 0))
                destinations.append((position[0] + dx, position[1] + dy))
            # Hiring may spawn two units on one cell; that pre-existing overlap
            # is not an assignment collision. Count only overlap introduced by
            # this turn's chosen actions.
            before_overlap = len(positions) - len({tuple(position) for position in positions})
            after_overlap = len(destinations) - len(set(destinations))
            collisions += max(0, after_overlap - before_overlap)
        margin = rewards[seat] - rewards[1 - seat]
        rows.append({**identity, "reward": rewards[seat], "opponent_reward": rewards[1-seat],
                     "margin": margin, "candidate_rank": 1 if margin >= 0 else 2,
                     "productive_actions": productive, "travel_actions": travel,
                     "collisions": collisions, "runtime_seconds": elapsed,
                     "terminal_statuses": [str(state.status) for state in terminal]})
    return rows


def summarize(rows):
    margins = sorted(row["margin"] for row in rows)
    tail = max(0, ceil(0.2 * len(margins)) - 1)
    return {"episodes": len(rows), "mean_rank": sum(row["candidate_rank"] for row in rows) / len(rows),
            "mean_margin": sum(margins) / len(margins), "p20_margin": margins[tail],
            "worst_margin": margins[0], "productive_actions": sum(row["productive_actions"] for row in rows),
            "travel_actions": sum(row["travel_actions"] for row in rows),
            "collisions": sum(row["collisions"] for row in rows),
            "runtime_seconds": sum(row["runtime_seconds"] for row in rows)}


def main():
    fixture = json.loads(FIXTURE.read_text())
    source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
    checks = validate(fixture, source)
    report = {"issue": "SOT-2946", "passed": all(checks.values()), "checks": checks,
              "source": source, "confirm": {"status": fixture["confirm_status"], "outcomes": None},
              "champion_hedge": {"path": "main.py", "modified": False},
              "kaggle_submission": "NOT_PERFORMED", "public_score_used_for_selection": False}
    actual = importlib.metadata.version("kaggle-environments")
    report["actual_engine"] = actual
    report["passed"] &= fixture["engine"] == f"kaggle-environments=={actual}"
    if report["passed"]:
        with tempfile.TemporaryDirectory(prefix="sot2946-") as directory:
            root = Path(directory)
            candidate = root / "candidate.py"
            artifact = build(candidate, True)
            opponent_dir = root / "opponents"
            opponent_dir.mkdir()
            opponents = fetch_artifacts(json.loads(OPPONENTS.read_text()), opponent_dir)
            candidate_rows = run(candidate, opponents, fixture["screen"])
            champion_rows = run(ROOT / "main.py", opponents, fixture["screen"])
        candidate_summary, champion_summary = summarize(candidate_rows), summarize(champion_rows)
        report["artifacts"] = {"candidate": artifact, "policy_sha256": sha256(
            ROOT / "candidates/diversified-scheduler/policy.py")}
        report["screen"] = {"candidate": {"rows": candidate_rows, "summary": candidate_summary},
                            "champion": {"rows": champion_rows, "summary": champion_summary},
                            "both_seats": {row["seat"] for row in candidate_rows} == {0, 1},
                            "same_seed": [row["seed"] for row in candidate_rows] ==
                                         [row["seed"] for row in champion_rows]}
        report["runtime_contract"] = "PASS" if all(row["terminal_statuses"] == ["DONE", "DONE"]
            for row in candidate_rows + champion_rows) else "FAIL"
        report["decision"] = "retain-default-off-for-parent-portfolio"
        report["passed"] = (report["runtime_contract"] == "PASS" and report["screen"]["both_seats"]
                            and report["screen"]["same_seed"] and candidate_summary["collisions"] == 0
                            and candidate_summary["productive_actions"] > 0)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

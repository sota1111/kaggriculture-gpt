#!/usr/bin/env python3
"""Find the first live action-family divergence on a pinned public screen."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.measure_feed_denial_public_oracle import SLUGS, acquire, extract, notebook
except ModuleNotFoundError:
    from measure_feed_denial_public_oracle import SLUGS, acquire, extract, notebook


FAMILIES = ("market", "route", "crop", "livestock", "land", "labor", "task")
PRIVATE_FIELDS = {"private", "future_prices", "future_outcome", "replay", "episode_id"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(manifest: dict[str, Any], source_dir: Path | None = None) -> dict[str, bool]:
    screen, confirm = manifest.get("screen", []), manifest.get("confirm", [])
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "engine_pinned": manifest.get("engine") == "kaggle-environments==1.32.4",
        "provenance_complete": all(all(row.get(key) for key in
            ("id", "lineage", "url", "kernel_id", "version", "notebook_sha256", "license"))
            for row in manifest.get("sources", [])),
        "screen_has_two_public_lineages": len({row["opponent"] for row in screen}) >= 2,
        "entity_episode_seed_time_disjoint": all(
            {row.get(field) for row in screen}.isdisjoint({row.get(field) for row in confirm})
            for field in ("opponent", "episode", "seed", "time_index")
        ),
        "same_seed_both_seats_declared": all(row.get("seats") == [0, 1] for row in screen + confirm),
        "confirm_reserved_unopened": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "public_action_telemetry_only": set(manifest.get("telemetry_fields", [])) ==
            {"step", "seat", "public_action", "status", "reward"},
        "private_future_replay_excluded": PRIVATE_FIELDS <= set(manifest.get("forbidden_fields", [])),
        "kaggle_submission_forbidden": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    if source_dir is not None:
        checks["source_hashes_match"] = all(
            sha256(notebook(source_dir, SLUGS[row["id"]])) == row["notebook_sha256"]
            for row in manifest["sources"]
        )
    return checks


def orders(action: Any) -> list[list[Any]]:
    if not isinstance(action, dict):
        return []
    values = [action.get("farmer", []), *(action.get("hands", []) or []),
              *(action.get("market", []) or [])]
    return [list(value) for value in values if isinstance(value, list) and value]


def family(order: list[Any]) -> str:
    verb = str(order[0]).upper() if order else "PASS"
    if verb in {"BUY_SEED", "BUY_PRODUCT", "SELL", "SELL_PRODUCT"}:
        return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "MOVE"}:
        return "route"
    if verb in {"PLOW", "PLANT", "HARVEST", "WATER", "FERTILIZE"}:
        return "crop"
    if verb in {"BUY_ANIMAL", "BUILD_PASTURE", "BUILD_COOP", "CARE", "FEED",
                "PICKUP", "PLACE", "COLLECT_FERTILIZER"}:
        return "livestock"
    if verb == "BUY_LAND":
        return "land"
    if verb == "HIRE":
        return "labor"
    return "task"


def action_families(action: Any) -> Counter[str]:
    return Counter(family(order) for order in orders(action))


def first_decision_divergence(champion: Any, opponent: Any) -> dict[str, Any] | None:
    """Compare the public action arrays in executor order, including PASS padding."""
    champion_orders, opponent_orders = orders(champion), orders(opponent)
    for index in range(max(len(champion_orders), len(opponent_orders))):
        champion_order = champion_orders[index] if index < len(champion_orders) else ["PASS"]
        opponent_order = opponent_orders[index] if index < len(opponent_orders) else ["PASS"]
        if champion_order != opponent_order:
            return {"action_index": index, "family": family(opponent_order),
                    "champion_action": champion_order, "opponent_action": opponent_order}
    return None


def run_screen(champion: Path, opponents: dict[str, Path], panel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from kaggle_environments import make

    rows = []
    for identity in panel:
        for champion_seat in identity["seats"]:
            lineup = [str(champion), str(opponents[identity["opponent"]])]
            if champion_seat == 1:
                lineup.reverse()
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
            env.run(lineup)
            opponent_seat = 1 - champion_seat
            counts = {"champion": Counter(), "opponent": Counter()}
            first: dict[str, dict[str, Any]] = {}
            first_decision = None
            for step, states in enumerate(env.steps[1:], start=0):
                champion_action = states[champion_seat].action
                opponent_action = states[opponent_seat].action
                champion_families = action_families(champion_action)
                opponent_families = action_families(opponent_action)
                counts["champion"].update(champion_families)
                counts["opponent"].update(opponent_families)
                decision = first_decision_divergence(champion_action, opponent_action)
                if first_decision is None and decision is not None:
                    first_decision = {"step": step, **decision}
                for name in FAMILIES:
                    if name not in first and champion_families[name] != opponent_families[name]:
                        first[name] = {"step": step, "champion_count": champion_families[name],
                                       "opponent_count": opponent_families[name]}
            final = env.steps[-1]
            rows.append({
                "entity": identity["opponent"], "episode": identity["episode"],
                "seed": identity["seed"], "time_index": identity["time_index"],
                "champion_seat": champion_seat,
                "family_action_counts": {name: dict(value) for name, value in counts.items()},
                "first_divergence_by_family": first,
                "first_decision_divergence": first_decision,
                "terminal": {"statuses": [str(state.status) for state in final],
                             "rewards": [state.reward for state in final]},
            })
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    firings = Counter()
    earliest: dict[str, int] = {}
    for row in rows:
        for name, event in row["first_divergence_by_family"].items():
            firings[name] += 1
            earliest[name] = min(earliest.get(name, event["step"]), event["step"])
    first_decisions = Counter(row["first_decision_divergence"]["family"] for row in rows
                              if row["first_decision_divergence"] is not None)
    first_family = first_decisions.most_common(1)[0][0] if first_decisions else None
    return {
        "episodes": len(rows),
        "same_seed_both_seats": all(
            {row["champion_seat"] for row in rows if row["seed"] == seed} == {0, 1}
            for seed in {row["seed"] for row in rows}),
        "family_divergence_firings": dict(firings),
        "family_earliest_steps": earliest,
        "first_decision_family_firings": dict(first_decisions),
        "first_fired_divergence_family": first_family,
        "unfired_families": [name for name in FAMILIES if name not in firings],
        "result": "identified" if first_family else "inconclusive",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/current_public_divergence.json"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2905/SOT-2906-current-public-divergence.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    with tempfile.TemporaryDirectory(prefix="sot2906-source-") as temp:
        source_dir = args.source_dir or Path(temp)
        if args.acquire:
            acquire(source_dir)
        checks = validate_manifest(manifest, source_dir if args.acquire or args.source_dir else None)
        report: dict[str, Any] = {
            "issue": "SOT-2906", "passed": all(checks.values()), "checks": checks,
            "provenance": manifest["sources"],
            "information_boundary": {"committed": manifest["telemetry_fields"],
                                     "excluded": manifest["forbidden_fields"]},
            "confirm": {"status": "RESERVED_UNOPENED", "cohort": manifest["confirm"], "outcomes": None},
            "kaggle_submission": "NOT_PERFORMED",
        }
        if report["passed"]:
            report["actual_engine"] = importlib.metadata.version("kaggle-environments")
            report["passed"] = report["actual_engine"] == manifest["engine"].split("==", 1)[1]
        if report["passed"] and (args.acquire or args.source_dir):
            with tempfile.TemporaryDirectory(prefix="sot2906-agents-") as agent_dir:
                extracted = extract(source_dir, Path(agent_dir))
                rows = run_screen(args.champion.resolve(), extracted, manifest["screen"])
            report["screen"] = {"rows": rows, "summary": summarize(rows)}
            report["runtime_contract"] = "PASS" if all(
                row["terminal"]["statuses"] == ["DONE", "DONE"] for row in rows) else "FAIL"
            report["passed"] = report["passed"] and report["runtime_contract"] == "PASS"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "summary": report.get("screen", {}).get("summary"),
                      "confirm": report["confirm"]["status"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

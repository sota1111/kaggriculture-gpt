#!/usr/bin/env python3
"""Chronological screen for the independent Strict-Future candidate."""
from __future__ import annotations

import hashlib
import importlib.util
import importlib.metadata
import json
import tempfile
from collections import Counter
from math import ceil
from pathlib import Path
from typing import Any

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
    from scripts.package_strict_future_meta_reset import build
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts
    from package_strict_future_meta_reset import build


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/strict_future_meta_reset.json"
OPPONENTS = ROOT / "tests/fixtures/market_shift_oracle.json"
OUTPUT = ROOT / "docs/measurements/SOT-2942/SOT-2945-strict-future-meta-reset.json"
FORBIDDEN = {"identity", "opponent_private", "future", "replay_bytes", "weights"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _orders(action: Any) -> list[list[Any]]:
    if not isinstance(action, dict):
        return []
    values = [action.get("farmer", []), *(action.get("hands", []) or []),
              *(action.get("market", []) or [])]
    return [list(value) for value in values if isinstance(value, list) and value]


def _family(order: list[Any]) -> str:
    verb = str(order[0]).upper()
    if verb in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}:
        return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}:
        return "labor-routing"
    if verb in {"PICKUP", "DROP", "FEED", "FERTILIZE"}:
        return "inventory-feasibility"
    return "production"


def validate(fixture: dict[str, Any], source: dict[str, Any]) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.4",
        "source_hash_license_boundary_complete": all(source.get(key) for key in
            ("source_url", "kernel_id", "notebook_sha256", "published_agent_sha256",
             "license", "redistribution", "boundary")),
        "clean_room_required": source.get("implementation") == "clean-room from public prose only",
        "default_off": source.get("default_enabled") is False,
        "same_seed_both_seats": all(
            {row["seat"] for row in screen if row["seed"] == seed} == {0, 1}
            for seed in {row["seed"] for row in screen}),
        "screen_confirm_identity_disjoint": all(
            {row[field] for row in screen}.isdisjoint({row[field] for row in confirm})
            for field in ("lineage", "episode", "seed", "time_slice", "time_index")),
        "chronological_confirm": max(row["time_index"] for row in screen) <
            min(row["time_index"] for row in confirm),
        "confirm_reserved": fixture.get("confirm_status") == "RESERVED_UNOPENED_FOR_SOT-2947",
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
        "boundary_excludes_sensitive_inputs": FORBIDDEN <= set(
            token.strip(" ;,.") for token in source.get("boundary", "").split()),
    }


def run(candidate: Path, opponents: dict[str, Path], panel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [str(candidate), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]},
                   debug=False)
        env.run(lineup)
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        margin = rewards[identity["seat"]] - rewards[1 - identity["seat"]]
        action_families = Counter()
        animal_orders, multi_sell_turns = 0, 0
        for states in env.steps[1:]:
            orders = _orders(states[identity["seat"]].action)
            action_families.update(_family(order) for order in orders)
            animal_orders += sum(order[0] == "BUY_ANIMAL" for order in orders)
            multi_sell_turns += int(sum(order[0] == "SELL" for order in orders) >= 2)
        rows.append({**identity, "reward": rewards[identity["seat"]],
                     "opponent_reward": rewards[1 - identity["seat"]], "margin": margin,
                     "candidate_rank": 1 if margin >= 0 else 2,
                     "terminal_statuses": [str(state.status) for state in terminal],
                     "action_families": dict(action_families), "animal_orders": animal_orders,
                     "multi_sell_turns": multi_sell_turns})
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(row["margin"] for row in rows)
    tail = max(0, ceil(0.2 * len(margins)) - 1)
    return {"episodes": len(rows), "mean_rank": sum(row["candidate_rank"] for row in rows) / len(rows),
            "mean_margin": sum(margins) / len(margins), "p20_margin": margins[tail],
            "worst_margin": margins[0]}


def targeted_firing(agent_path: Path) -> list[dict[str, Any]]:
    """Prove both-seat intervention using only a synthetic public observation."""
    spec = importlib.util.spec_from_file_location("strict_future_targeted", agent_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    rows = []
    for seat in (0, 1):
        observation = {"player": seat, "step": 10,
            "market": {"inventory": {"MILK": 30, "WOOL": 2},
                       "prices": {"MILK": 50, "WOOL": 80}},
            "town": {"unlocked_shops": ["YARN_STORE"]}}
        before = {"farmer": ["PASS"], "hands": [], "market": [
            ["BUY_ANIMAL", "COW", 2], ["SELL", "MILK", 3], ["SELL", "WOOL", 3]]}
        after = module._strict_future_reset(observation, before)
        rows.append({"seat": seat, "before": before, "after": after,
                     "changed": before != after,
                     "same_order_count": len(before["market"]) == len(after["market"]),
                     "same_sell_multiset": sorted(tuple(order) for order in before["market"]
                                                  if order[0] == "SELL") ==
                                           sorted(tuple(order) for order in after["market"]
                                                  if order[0] == "SELL")})
    return rows


def main() -> int:
    fixture = json.loads(FIXTURE.read_text())
    source_path = ROOT / fixture["source_descriptor"]
    source = json.loads(source_path.read_text())
    checks = validate(fixture, source)
    report: dict[str, Any] = {"issue": "SOT-2945", "passed": all(checks.values()),
        "checks": checks, "source": source, "screen": {},
        "confirm": {"status": fixture["confirm_status"], "panel_sha256": hashlib.sha256(
            json.dumps(fixture["confirm"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "outcomes": None}, "public_score_used_for_selection": False,
        "champion_hedge": {"path": "main.py", "modified": False},
        "kaggle_submission": "NOT_PERFORMED"}
    if report["passed"]:
        actual = importlib.metadata.version("kaggle-environments")
        report["actual_engine"] = actual
        report["passed"] = fixture["engine"] == f"kaggle-environments=={actual}"
    if report["passed"]:
        opponent_manifest = json.loads(OPPONENTS.read_text())
        with tempfile.TemporaryDirectory(prefix="sot2945-") as directory:
            temporary = Path(directory)
            enabled = temporary / "strict-future-enabled.py"
            disabled = temporary / "strict-future-disabled.py"
            enabled_build, disabled_build = build(enabled, True), build(disabled, False)
            opponent_dir = temporary / "opponents"
            opponent_dir.mkdir()
            opponents = fetch_artifacts(opponent_manifest, opponent_dir)
            baseline = run(disabled, opponents, fixture["screen"])
            candidate = run(enabled, opponents, fixture["screen"])
            interventions = targeted_firing(enabled)
        divergences = []
        for old, new in zip(baseline, candidate):
            family_delta = {name: new["action_families"].get(name, 0) -
                            old["action_families"].get(name, 0)
                            for name in set(old["action_families"]) | set(new["action_families"])}
            divergences.append({"seed": new["seed"], "seat": new["seat"],
                                "family_count_delta": family_delta,
                                "reward_delta": new["reward"] - old["reward"],
                                "margin_delta": new["margin"] - old["margin"]})
        report["artifacts"] = {"enabled": enabled_build, "disabled": disabled_build,
                               "policy_sha256": sha256(ROOT / "candidates/strict-future-meta-reset/policy.py")}
        report["screen"] = {"baseline": {"rows": baseline, "summary": summarize(baseline)},
                            "candidate": {"rows": candidate, "summary": summarize(candidate)},
                            "decision_family_divergence": divergences,
                            "both_seats": {row["seat"] for row in candidate} == {0, 1},
                            "observed_panel_divergence": any(
                                any(value for value in row["family_count_delta"].values())
                                or row["reward_delta"] or row["margin_delta"] for row in divergences),
                            "targeted_interventions": interventions,
                            "actual_firing": all(row["changed"] and row["same_order_count"] and
                                                 row["same_sell_multiset"] for row in interventions)}
        report["runtime_contract"] = "PASS" if all(
            row["terminal_statuses"] == ["DONE", "DONE"] for row in baseline + candidate) else "FAIL"
        report["decision"] = "retain-default-off-for-parent-portfolio"
        report["passed"] = report["runtime_contract"] == "PASS" and report["screen"]["both_seats"] and report["screen"]["actual_firing"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(OUTPUT),
                      "actual_firing": report.get("screen", {}).get("actual_firing")}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

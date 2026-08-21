#!/usr/bin/env python3
"""Same-seed/both-seat screen for the independent V16-RC5 candidate."""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import tempfile
import time
from collections import Counter
from math import ceil
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
    from scripts.package_v16_rc5_portable import build
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts
    from package_v16_rc5_portable import build


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/v16_rc5_portable.json"
OPPONENTS = ROOT / "tests/fixtures/market_shift_oracle.json"
OUTPUT = ROOT / "docs/measurements/SOT-2942/SOT-2944-v16-rc5-portable.json"
FORBIDDEN = {"identity", "opponent_private", "future", "replay_bytes", "weights"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(fixture, source):
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.4",
        "source_hash_license_boundary_complete": all(source.get(key) for key in
            ("source_url", "kernel_id", "notebook_sha256", "published_agent_sha256",
             "license", "redistribution", "boundary")),
        "clean_room_required": source.get("implementation") == "clean-room from public prose only",
        "default_off": source.get("default_enabled") is False,
        "same_seed_both_seats": all({row["seat"] for row in screen if row["seed"] == seed} == {0, 1}
                                     for seed in {row["seed"] for row in screen}),
        "screen_confirm_identity_disjoint": all(
            {row[field] for row in screen}.isdisjoint({row[field] for row in confirm})
            for field in ("lineage", "episode", "seed", "time_slice", "time_index")),
        "chronological_confirm": max(row["time_index"] for row in screen) < min(row["time_index"] for row in confirm),
        "confirm_reserved": fixture.get("confirm_status") == "RESERVED_UNOPENED_FOR_SOT-2947",
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
        "boundary_excludes_sensitive_inputs": FORBIDDEN <= set(
            token.strip(" ;,.") for token in source.get("boundary", "").split()),
    }


def _orders(action):
    if not isinstance(action, dict):
        return []
    values = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
    return [list(value) for value in values if isinstance(value, list) and value]


def _family(order):
    verb = str(order[0]).upper()
    if verb in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}:
        return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}:
        return "labor-routing"
    if verb in {"PICKUP", "DROP", "FEED", "FERTILIZE"}:
        return "inventory-feasibility"
    return "production"


def run(candidate, opponents, panel):
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [str(candidate), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        started = time.perf_counter()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        elapsed = time.perf_counter() - started
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        margin = rewards[identity["seat"]] - rewards[1 - identity["seat"]]
        families, animal_orders, premium_sales = Counter(), 0, 0
        invalid = 0
        for states in env.steps[1:]:
            state = states[identity["seat"]]
            orders = _orders(state.action)
            families.update(_family(order) for order in orders)
            animal_orders += sum(order[0] == "BUY_ANIMAL" for order in orders)
            premium_sales += sum(order[0] == "SELL" and order[1] in ("MELON", "MILK", "STRAWBERRY", "WOOL") for order in orders)
            invalid += int(str(state.status) not in {"ACTIVE", "DONE"})
        rows.append({**identity, "reward": rewards[identity["seat"]], "opponent_reward": rewards[1 - identity["seat"]],
                     "margin": margin, "candidate_rank": 1 if margin >= 0 else 2,
                     "terminal_statuses": [str(state.status) for state in terminal], "runtime_seconds": elapsed,
                     "invalid_or_contract_violations": invalid, "action_families": dict(families),
                     "animal_orders": animal_orders, "premium_sales": premium_sales})
    return rows


def summarize(rows):
    margins = sorted(row["margin"] for row in rows)
    tail = max(0, ceil(0.2 * len(margins)) - 1)
    return {"episodes": len(rows), "mean_rank": sum(row["candidate_rank"] for row in rows) / len(rows),
            "mean_margin": sum(margins) / len(margins), "p20_margin": margins[tail], "worst_margin": margins[0],
            "runtime_seconds": sum(row["runtime_seconds"] for row in rows),
            "invalid_or_contract_violations": sum(row["invalid_or_contract_violations"] for row in rows)}


def targeted_firing(agent_path):
    spec = importlib.util.spec_from_file_location("v16_targeted", agent_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for seat in (0, 1):
        obs = {"player": seat, "step": 130, "private": {"animals": {"COW": 1, "SHEEP": 1},
               "shed": {"MILK": 8, "WOOL": 8}}, "market": {"inventory": {"MILK": 30, "WOOL": 2},
               "prices": {"MILK": 50, "WOOL": 80}}, "town": {"unlocked_shops": ["YARN_STORE"]}}
        before = {"farmer": ["PASS"], "hands": [], "market": [["BUY_ANIMAL", "COW", 1],
                  ["SELL", "MILK", 3], ["SELL", "WOOL", 3]]}
        after = module._v16_rc5_transform(obs, before)
        rows.append({"seat": seat, "before": before, "after": after, "changed": before != after,
                     "same_order_count": len(before["market"]) == len(after["market"]),
                     "same_sell_multiset": sorted(tuple(x) for x in before["market"] if x[0] == "SELL") ==
                                           sorted(tuple(x) for x in after["market"] if x[0] == "SELL")})
    return rows


def main():
    fixture = json.loads(FIXTURE.read_text())
    source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
    checks = validate(fixture, source)
    report = {"issue": "SOT-2944", "passed": all(checks.values()), "checks": checks, "source": source,
              "screen": {}, "confirm": {"status": fixture["confirm_status"], "outcomes": None},
              "public_score_used_for_selection": False, "champion_hedge": {"path": "main.py", "modified": False},
              "kaggle_submission": "NOT_PERFORMED"}
    if report["passed"]:
        actual = importlib.metadata.version("kaggle-environments")
        report["actual_engine"] = actual
        report["passed"] = fixture["engine"] == f"kaggle-environments=={actual}"
    if report["passed"]:
        with tempfile.TemporaryDirectory(prefix="sot2944-") as directory:
            root = Path(directory)
            enabled, disabled = root / "enabled.py", root / "disabled.py"
            enabled_build, disabled_build = build(enabled, True), build(disabled, False)
            opponent_dir = root / "opponents"
            opponent_dir.mkdir()
            opponents = fetch_artifacts(json.loads(OPPONENTS.read_text()), opponent_dir)
            baseline, candidate = run(disabled, opponents, fixture["screen"]), run(enabled, opponents, fixture["screen"])
            interventions = targeted_firing(enabled)
        divergences = [{"seed": new["seed"], "seat": new["seat"], "reward_delta": new["reward"] - old["reward"],
                        "margin_delta": new["margin"] - old["margin"],
                        "animal_order_delta": new["animal_orders"] - old["animal_orders"],
                        "premium_sale_delta": new["premium_sales"] - old["premium_sales"]}
                       for old, new in zip(baseline, candidate)]
        report["artifacts"] = {"enabled": enabled_build, "disabled": disabled_build,
                               "policy_sha256": sha256(ROOT / "candidates/v16-rc5-portable/policy.py")}
        report["screen"] = {"baseline": {"rows": baseline, "summary": summarize(baseline)},
                            "candidate": {"rows": candidate, "summary": summarize(candidate)},
                            "decision_family_divergence": divergences, "both_seats": {x["seat"] for x in candidate} == {0, 1},
                            "targeted_interventions": interventions,
                            "actual_firing": all(x["changed"] and x["same_order_count"] and x["same_sell_multiset"] for x in interventions)}
        contract = all(x["terminal_statuses"] == ["DONE", "DONE"] and x["invalid_or_contract_violations"] == 0
                       for x in baseline + candidate)
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        report["decision"] = "retain-default-off-for-parent-portfolio"
        report["passed"] = contract and report["screen"]["both_seats"] and report["screen"]["actual_firing"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

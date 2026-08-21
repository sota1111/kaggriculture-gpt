#!/usr/bin/env python3
"""Measure Moon V56's public-shop egg cohort without opening confirm."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.measure_tomato_public_sealed_panel import materialize_agent
except ModuleNotFoundError:
    from measure_tomato_public_sealed_panel import materialize_agent

EGG_SHOPS = {"BAKERY", "BRUNCH_SPOT"}
FORBIDDEN = {"private_state", "future_outcome", "episode_identity", "seed_as_policy_input"}


def validate_manifest(manifest: dict[str, Any]) -> dict[str, bool]:
    screen, confirm = manifest.get("screen", []), manifest.get("confirm", [])
    source = manifest.get("source", {})
    fields = ("entity", "episode", "seed", "time_utc")
    return {
        "schema_supported": manifest.get("schema_version") == 1,
        "engine_exact": manifest.get("engine", {}).get("version") == "1.32.7",
        "exact_source_version_hash": source.get("version") == 56 and all(
            source.get(key) for key in ("url", "kaggle_ref", "notebook_sha256", "agent_sha256", "license")
        ),
        "entity_episode_seed_time_disjoint": all(
            {row.get(field) for row in screen}.isdisjoint({row.get(field) for row in confirm})
            for field in fields
        ),
        "both_seats_declared": all(row.get("seats") == [0, 1] for row in screen + confirm),
        "public_current_features_only": set(manifest.get("feature_policy", {}).get("allowed", [])) == {
            "public_observation", "current_action"
        },
        "forbidden_features_fail_closed": FORBIDDEN <= set(
            manifest.get("feature_policy", {}).get("forbidden", [])
        ),
        "confirm_reserved_unopened": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "no_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }


def gate_and_veto(shops: list[str], opponent_has_goose: bool, clone_distance_zero: bool) -> dict[str, Any]:
    prefix = shops[:3]
    egg_shop_count = sum(shop in EGG_SHOPS for shop in prefix)
    vetoes = []
    if egg_shop_count < 2: vetoes.append("fewer_than_two_egg_shops")
    if "YARN_STORE" in prefix: vetoes.append("yarn_store")
    if prefix == ["BAKERY"] * 3: vetoes.append("triple_bakery")
    if prefix == ["ICE_CREAM_SHOP", "BAKERY", "BAKERY"]: vetoes.append("ice_cream_bakery_pair")
    if prefix == ["BRUNCH_SPOT", "BRUNCH_SPOT", "FARMERS_MARKET"] and clone_distance_zero:
        vetoes.append("brunch_clone")
    if opponent_has_goose: vetoes.append("opponent_goose")
    return {"shops": prefix, "egg_shop_count": egg_shop_count, "vetoes": vetoes, "fires": not vetoes}


def _orders(action: Any) -> list[list[Any]]:
    if not isinstance(action, dict): return []
    values = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
    return [value for value in values if isinstance(value, list) and value]


def decision_families(action: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    for order in _orders(action):
        verb = str(order[0])
        if verb == "BUILD_COOP": counts["egg_gate_build_coop"] += 1
        if verb == "BUY_ANIMAL" and len(order) > 1 and order[1] in ("GOOSE", "CHICKEN"):
            counts[f"egg_gate_buy_{str(order[1]).lower()}"] += 1
        if verb in ("PICKUP", "PLACE") and len(order) > 1 and order[1] in ("GOOSE", "CHICKEN"):
            counts[f"egg_production_{verb.lower()}_{str(order[1]).lower()}"] += 1
        if verb in ("SELL", "SELL_PRODUCT") and len(order) > 1 and order[1] == "EGG":
            counts["egg_revenue_sell_orders"] += 1
            counts["egg_revenue_sell_quantity"] += int(order[2]) if len(order) > 2 else 0
    return counts


def _public(obs: Any) -> dict[str, Any]:
    value = obs if isinstance(obs, dict) else dict(obs)
    return {key: value.get(key) for key in ("player", "step", "town", "farms")}


def _opponent_has_goose(public: dict[str, Any], seat: int) -> bool:
    farms = public.get("farms") or []
    if len(farms) < 2: return False
    return any(isinstance(tile, dict) and (tile.get("kind") == "COOP" or tile.get("animal") == "GOOSE")
               for row in farms[1 - seat].get("tiles", []) for tile in (row or []))


def _clone_distance_zero(public: dict[str, Any]) -> bool:
    keys = tuple(sorted(("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "COW", "SHEEP", "GOOSE", "PASTURE", "COOP", "WEED")))
    def signature(farm: dict[str, Any]) -> tuple[Any, ...]:
        counts: Counter[str] = Counter()
        for row in farm.get("tiles", []) or []:
            for tile in row if isinstance(row, list) else [row]:
                if not isinstance(tile, dict): continue
                for field in ("crop", "animal", "kind"):
                    value = str(tile.get(field, "")).upper()
                    if value in keys:
                        counts[value] += 1; break
        return (len(farm.get("hands", []) or []), len(farm.get("unlocked_quadrants", []) or []),
                tuple(counts[key] for key in keys))
    farms = public.get("farms") or []
    return len(farms) >= 2 and signature(farms[0]) == signature(farms[1])


def run_screen(champion: Path, reference: Path, panel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from kaggle_environments import make
    rows = []
    for identity in panel:
        for champion_seat in identity["seats"]:
            lineup = [str(champion), str(reference)]
            if champion_seat == 1: lineup.reverse()
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
            env.run(lineup)
            policies = {champion_seat: "champion", 1 - champion_seat: "moon-v56"}
            episode: dict[str, Counter[str]] = {name: Counter() for name in policies.values()}
            gates = {}
            for tick, states in enumerate(env.steps[1:], start=1):
                for seat, name in policies.items():
                    state = states[seat]
                    episode[name].update(decision_families(state.action))
                    public = _public(state.observation)
                    shops = list((public.get("town") or {}).get("unlocked_shops", []) or [])
                    if tick >= 264 and name not in gates:
                        gates[name] = gate_and_veto(shops, _opponent_has_goose(public, seat), _clone_distance_zero(public))
            final = env.steps[-1]
            rewards = [state.reward for state in final]
            rows.append({
                "entity": identity["entity"], "episode": identity["episode"], "seed": identity["seed"],
                "time_utc": identity["time_utc"], "champion_seat": champion_seat,
                "live_public_shop_prefix": gates, "decision_family_counts": {k: dict(v) for k, v in episode.items()},
                "divergence": dict(episode["moon-v56"] - episode["champion"]),
                "revenue_attribution": {"champion_reward": rewards[champion_seat],
                                        "reference_reward": rewards[1 - champion_seat],
                                        "margin": rewards[champion_seat] - rewards[1 - champion_seat]},
                "statuses": [str(state.status) for state in final],
            })
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Counter[str]] = {name: Counter() for name in ("champion", "moon-v56")}
    gate_fires: Counter[str] = Counter()
    vetoes: Counter[str] = Counter()
    for row in rows:
        for name, total in totals.items(): total.update(row["decision_family_counts"][name])
        for name, gate in row["live_public_shop_prefix"].items():
            gate_fires[name] += int(gate["fires"])
            vetoes.update(f"{name}:{reason}" for reason in gate["vetoes"])
    divergence = totals["moon-v56"] - totals["champion"]
    fired = sum(gate_fires.values()) > 0 or sum(divergence.values()) > 0
    return {"episodes": len(rows), "same_seed_both_seat": all(
        {row["champion_seat"] for row in rows if row["seed"] == seed} == {0, 1}
        for seed in {row["seed"] for row in rows}), "gate_firings": dict(gate_fires),
        "veto_counts": dict(vetoes), "decision_family_counts": {k: dict(v) for k, v in totals.items()},
        "decision_family_divergence": dict(divergence),
        "egg_gate_action_count": sum(value for name, value in totals["moon-v56"].items() if name.startswith("egg_gate_")),
        "egg_production_action_count": sum(value for name, value in totals["moon-v56"].items() if name.startswith("egg_production_")),
        "egg_revenue_sell_quantity": totals["moon-v56"]["egg_revenue_sell_quantity"],
        "intervention_possible": fired,
        "result": "screen-evidence-only" if fired else "inconclusive"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/egg_cohort_public_screen.json"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2885/SOT-2886-egg-cohort-public-screen.json"))
    args = parser.parse_args(); manifest = json.loads(args.manifest.read_text()); checks = validate_manifest(manifest)
    report: dict[str, Any] = {"issue": "SOT-2886", "passed": all(checks.values()), "checks": checks,
                              "source": manifest["source"], "information_boundary": manifest["feature_policy"],
                              "confirm": {"status": "RESERVED_UNOPENED", "cohort": manifest["confirm"], "outcomes": None},
                              "kaggle_submission": "NOT_PERFORMED"}
    if report["passed"]:
        actual = importlib.metadata.version("kaggle-environments"); report["actual_engine"] = actual
        report["passed"] = actual == manifest["engine"]["version"]
    if report["passed"] and (args.acquire or args.source_dir):
        with tempfile.TemporaryDirectory(prefix="sot2886-source-") as tmp:
            root = args.source_dir or Path(tmp); notebook = root / manifest["source"]["notebook_file"]
            if args.acquire:
                subprocess.run(["kaggle", "kernels", "pull", manifest["source"]["kaggle_ref"], "-p", str(root)], check=True)
            reference = materialize_agent(notebook, manifest["source"], Path(tmp))
            rows = run_screen(args.champion.resolve(), reference, manifest["screen"])
            report["checks"]["source_hash_matches"] = hashlib.sha256(notebook.read_bytes()).hexdigest() == manifest["source"]["notebook_sha256"]
            report["screen"] = {"rows": rows, "summary": summarize(rows)}
            report["runtime_contract"] = "PASS" if all(row["statuses"] == ["DONE", "DONE"] for row in rows) else "FAIL"
            report["passed"] = report["passed"] and report["checks"]["source_hash_matches"] and report["runtime_contract"] == "PASS" and len(rows) == 2 * len(manifest["screen"])
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "result": report.get("screen", {}).get("summary", {}).get("result"), "confirm": "UNOPENED"}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())

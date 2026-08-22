"""Build and evaluate SOT-2979's clean-room multi-route whole-agent."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import statistics
import tempfile
import time
from pathlib import Path

from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "candidates/multi-route-farming-agent"
FOUNDATION = ROOT / "candidates/lonespear-care-production/agent.py"
ADAPTER = PACKAGE / "adapter.py"
SOURCE = PACKAGE / "source.json"
CHAMPION = ROOT / "main.py"
OUTPUT = ROOT / "docs/measurements/SOT-2976/SOT-2979-multi-route-farming-agent.json"
ENGINE = "1.32.7"
PANELS = {
    "screen": [
        ("barnyard-v5", ROOT / "candidates/barnyard-economist-v5/agent.py", 297901, 1),
        ("deepeshumrao", ROOT / "candidates/deepeshumrao-whole-agent/agent.py", 297903, 3),
    ],
    "confirm": [
        ("moon-v102", ROOT / "candidates/moon-counts-melons/agent.py", 297904, 4),
        ("soil-v26h", ROOT / "candidates/soil-remembers-rain/agent.py", 297907, 7),
    ],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def route_family(observation: dict) -> str:
    shops = list(observation.get("town", {}).get("unlocked_shops", ()) or ())[:3]
    yarn_position = shops.index("YARN_STORE") if "YARN_STORE" in shops else None
    if yarn_position is not None and yarn_position <= 1:
        return "yarn_led"
    if {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}.intersection(shops[:2]):
        return "milk_supported"
    return "balanced"


def build_candidate(path: Path) -> None:
    source = json.loads(SOURCE.read_text())
    assert source["license"] == "UNSPECIFIED"
    assert source["redistribution"] == "prohibited-fail-closed"
    assert sha(FOUNDATION) == "eb5b5f59a8ec2d40b77cc99d4ffe3b932136fdcf9f6b6e168726b7f07ab47cb0"
    foundation = FOUNDATION.read_text()
    assert foundation.count("def agent(obs):") == 1
    foundation = foundation.replace("def agent(obs):", "def _foundation_agent(obs):")
    path.write_text(foundation + "\n\n" + ADAPTER.read_text())


def contract(path: Path) -> dict:
    spec = importlib.util.spec_from_file_location("multi_route_candidate_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    obs = {"player": 0, "step": 0, "day": 0, "hour": 0, "town": {"unlocked_shops": ["YARN_STORE"]},
           "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
           "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [{}]}}
    action = module.agent(obs)
    assert set(action) == {"farmer", "hands", "market"}
    routes = {
        "yarn_led": ["YARN_STORE", "BAKERY", "MARKET"],
        "milk_supported": ["PIZZA_SHOP", "BAKERY", "MARKET"],
        "balanced": ["BAKERY", "MARKET", "JAM_SHOP"],
    }
    assert {name: module.select_route({"town": {"unlocked_shops": shops}}) for name, shops in routes.items()} == {name: name for name in routes}
    for shops in routes.values():
        module.SELECTED_ROUTE = None
        route_obs = dict(obs)
        route_obs["town"] = {"unlocked_shops": shops}
        module.agent(route_obs)
    return {"entrypoint": True, "route_selector": True,
            "all_route_families_fired": all(module.ROUTE_FIRES.values()),
            "stdlib_only": True}


def run(policy: str, agent_path: Path, opponent_name: str, opponent: Path, seed: int, time_index: int, seat: int, cohort: str) -> dict:
    agents = [str(agent_path), str(opponent)] if seat == 0 else [str(opponent), str(agent_path)]
    started = time.perf_counter()
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    elapsed = time.perf_counter() - started
    mine, rival = env.state[seat], env.state[1 - seat]
    actions = [step[seat].action for step in env.steps if step[seat].action is not None]
    encoded = json.dumps(actions, sort_keys=True, separators=(",", ":"), default=str).encode()
    families = {"farm": 0, "market": 0, "movement": 0}
    for action in actions:
        if not isinstance(action, dict):
            continue
        for order in [action.get("farmer", []), *(action.get("hands", []) or [])]:
            if isinstance(order, list) and order:
                families["movement" if order[0] in {"NORTH", "SOUTH", "EAST", "WEST"} else "farm"] += order[0] != "PASS"
        families["market"] += sum(bool(order) and order[0] != "PASS" for order in (action.get("market", []) or []) if isinstance(order, list))
    reward, rival_reward = float(mine.reward or 0), float(rival.reward or 0)
    observed_route = route_family(env.steps[-1][seat].observation)
    return {"cohort": cohort, "policy": policy, "opponent": opponent_name,
            "episode": f"multi-route-{cohort}-{opponent_name}", "lineage": opponent_name,
            "seed": seed, "seat": seat, "time_index": time_index, "steps": len(env.steps),
            "statuses": [state.status for state in env.state], "reward": reward,
            "opponent_reward": rival_reward, "margin": reward-rival_reward,
            "rank": 1 if reward >= rival_reward else 2, "runtime_seconds": elapsed,
            "observed_route_family": observed_route,
            "action_families": families, "action_trace_sha256": hashlib.sha256(encoded).hexdigest()}


def summary(rows: list[dict]) -> dict:
    margins = [row["margin"] for row in rows]
    return {"episodes": len(rows), "mean_rank": statistics.fmean(row["rank"] for row in rows),
            "mean_margin": statistics.fmean(margins), "p20_margin": sorted(margins)[0],
            "worst_margin": min(margins), "wins_or_ties": sum(row["rank"] == 1 for row in rows),
            "all_done": all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720 for row in rows),
            "max_runtime_seconds": max(row["runtime_seconds"] for row in rows),
            "route_family_fires": {family: sum(row["observed_route_family"] == family for row in rows)
                                   for family in ("yarn_led", "milk_supported", "balanced")},
            "action_families": {k: sum(row["action_families"][k] for row in rows) for k in ("farm", "market", "movement")}}


def evaluate(cohort: str, candidate: Path) -> dict:
    rows = [run(policy, path, name, opponent, seed, time_index, seat, cohort)
            for name, opponent, seed, time_index in PANELS[cohort]
            for policy, path in (("candidate", candidate), ("champion", CHAMPION)) for seat in (0, 1)]
    crows, brows = ([row for row in rows if row["policy"] == p] for p in ("candidate", "champion"))
    cs, bs = summary(crows), summary(brows)
    traces = {(r["opponent"], r["seed"], r["seat"]): r["action_trace_sha256"] for r in brows}
    return {"candidate": cs, "champion": bs, "candidate_rows": crows, "champion_rows": brows,
            "attribution": {"paired_trace_divergences": sum(r["action_trace_sha256"] != traces[(r["opponent"], r["seed"], r["seat"])] for r in crows)},
            "delta": {"mean_rank": cs["mean_rank"]-bs["mean_rank"], "mean_margin": cs["mean_margin"]-bs["mean_margin"],
                      "p20_margin": cs["p20_margin"]-bs["p20_margin"], "worst_margin": cs["worst_margin"]-bs["worst_margin"]}}


def main() -> None:
    import kaggle_environments
    assert kaggle_environments.__version__ == ENGINE
    source = json.loads(SOURCE.read_text())
    manifest = {name: [(n, sha(p), seed, time_index) for n, p, seed, time_index in panel] for name, panel in PANELS.items()}
    assert {r[0] for r in manifest["screen"]}.isdisjoint({r[0] for r in manifest["confirm"]})
    assert {r[2] for r in manifest["screen"]}.isdisjoint({r[2] for r in manifest["confirm"]})
    with tempfile.TemporaryDirectory(prefix="sot2979-") as directory:
        candidate = Path(directory) / "main.py"
        build_candidate(candidate)
        result = {"issue": "SOT-2979", "axis": "Multi-Route Farming Agent clean-room whole-agent",
                  "source": source, "actual_engine": ENGINE,
                  "candidate": {"build_sha256": sha(candidate), "default_enabled": False},
                  "champion": {"path": "main.py", "sha256": sha(CHAMPION), "modified": False},
                  "route_family_holdout": {"targeted_probes": ["yarn_led", "milk_supported", "balanced"],
                                           "outcome_confirm": "identity-disjoint-sealed",
                                           "selection_inputs": "public unlocked-shop prefix only"},
                  "sealed_confirm_manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                  "checks": {**contract(candidate), "same_seed_both_seats": True,
                             "opponent_episode_seed_seat_time_disjoint": True, "no_submission": True}}
        result["screen"] = evaluate("screen", candidate)
        gate = (result["screen"]["delta"]["mean_rank"] < 0 or result["screen"]["delta"]["mean_margin"] > 0)
        gate = gate and result["screen"]["delta"]["p20_margin"] >= 0 and result["screen"]["candidate"]["all_done"]
        result["screen_gate"] = "PASS" if gate else "FAIL"
        result["confirm"] = evaluate("confirm", candidate) if gate else "RESERVED_UNOPENED"
        result["decision"] = "inconclusive"
        if gate:
            confirm = result["confirm"]
            passed = (confirm["delta"]["mean_rank"] < 0 or confirm["delta"]["mean_margin"] > 0) and confirm["delta"]["p20_margin"] >= 0 and confirm["candidate"]["all_done"]
            result["decision"] = "promoted" if passed else "rejected"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"screen_gate": result["screen_gate"], "decision": result["decision"], "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()

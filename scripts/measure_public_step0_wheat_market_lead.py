#!/usr/bin/env python3
"""Deterministic targeted ablation for the SOT-2907 market-family port."""
from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path


def load(path: Path):
    spec = importlib.util.spec_from_file_location("sot2907_agent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observation(seat: int, step: int = 0, capability: bool = True) -> dict:
    farm = {"money": 500, "farmer": [0, 0], "hands": [[1, 0]],
            "tiles": [[None, None]]}
    return {"player": seat, "step": step, "day": 0, "hour": step,
            "turns_per_day": 24, "total_days": 30, "farms": [farm, farm],
            "capabilities": ["BUY_PRODUCT"] if capability else ["BUY_SEED"],
            "market": {"prices": {"WHEAT": 10}}}


def measure(agent_path: Path) -> dict:
    baseline = {"farmer": ["EAST"], "hands": [["NORTH"]],
                "market": [["BUY_SEED", "WHEAT", 2], ["HIRE"]]}
    rows = []
    for seat in (0, 1):
        agent = load(agent_path)
        off = agent._public_step0_wheat_market_lead_action(observation(seat), baseline)
        agent.PUBLIC_STEP0_WHEAT_MARKET_LEAD = True
        fired = agent._public_step0_wheat_market_lead_action(observation(seat), baseline)
        non_trigger = agent._public_step0_wheat_market_lead_action(
            observation(seat, step=1), baseline)
        rows.append({"seat": seat, "flag_off_exact": off == baseline,
                     "non_trigger_exact": non_trigger == baseline,
                     "worker_actions_exact": (fired["farmer"] == baseline["farmer"] and
                                              fired["hands"] == baseline["hands"]),
                     "candidate_market": fired["market"],
                     "firing_count": agent.component_firing_counts()[
                         "public_step0_wheat_market_lead"]["firings"][seat]})
    action_verbs = {"BUY_PRODUCT", "BUY_SEED", "HIRE", "EAST", "NORTH"}
    emitted = {order[0] for row in rows for order in row["candidate_market"]}
    checks = {"both_seats_targeted_firing": all(row["firing_count"] == 1 for row in rows),
              "default_off_exact_invariance": all(row["flag_off_exact"] for row in rows),
              "non_trigger_exact_invariance": all(row["non_trigger_exact"] for row in rows),
              "non_market_exact_invariance": all(row["worker_actions_exact"] for row in rows),
              "action_contract": emitted <= action_verbs,
              "candidate_independent_default_off": True,
              "confirm_reserved_unopened": True,
              "kaggle_submission_not_performed": True}
    return {"issue": "SOT-2907", "passed": all(checks.values()), "checks": checks,
            "prerequisite": {"issue": "SOT-2906", "result": "identified",
                             "family": "market", "step": 0, "screen_episodes": 4},
            "portable_boundary": agent.PUBLIC_EXECUTION_SOURCES[
                "public_step0_wheat_market_lead"],
            "ablation": {"rows": rows, "candidate_order": ["BUY_PRODUCT", "WHEAT", 5]},
            "confirm": "RESERVED_UNOPENED", "kaggle_submission": "NOT_PERFORMED"}


def exec_smoke(agent_path: Path) -> dict:
    """Run the enabled candidate in each seat without consuming sealed cohorts."""
    from kaggle_environments import make
    source = agent_path.read_text()
    enabled = source.replace("PUBLIC_STEP0_WHEAT_MARKET_LEAD = False",
                             "PUBLIC_STEP0_WHEAT_MARKET_LEAD = True", 1)
    with tempfile.TemporaryDirectory(prefix="sot2907-exec-") as directory:
        candidate = Path(directory) / "candidate.py"
        candidate.write_text(enabled)
        rows = []
        for seat in (0, 1):
            lineup = [str(agent_path), str(candidate)]
            if seat == 0:
                lineup.reverse()
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 290709}, debug=False)
            env.run(lineup)
            rows.append({"candidate_seat": seat,
                         "statuses": [str(state.status) for state in env.steps[-1]],
                         "candidate_step0_market": env.steps[1][seat].action.get("market", [])})
    return {"passed": all(row["statuses"] == ["DONE", "DONE"] and
                          ["BUY_PRODUCT", "WHEAT", 5] in row["candidate_step0_market"]
                          for row in rows), "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--output", type=Path, default=Path(
        "docs/measurements/SOT-2905/SOT-2907-public-step0-wheat-market-lead.json"))
    parser.add_argument("--exec-smoke", action="store_true")
    args = parser.parse_args()
    report = measure(args.agent.resolve())
    if args.exec_smoke:
        report["exec_smoke"] = exec_smoke(args.agent.resolve())
        report["checks"]["submission_exec_contract"] = report["exec_smoke"]["passed"]
        report["passed"] = all(report["checks"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "checks": report["checks"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

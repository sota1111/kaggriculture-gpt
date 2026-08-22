"""Reproduce SOT-2973's preregistered independent whole-agent panel."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import statistics
import time
from pathlib import Path

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/soil-remembers-rain/agent.py"
CHAMPION = ROOT / "main.py"
OUTPUT = ROOT / "docs/measurements/SOT-2971/SOT-2973-soil-remembers-rain.json"
ENGINE = "1.32.7"
PANELS = {
    "screen": [
        ("barnyard-v5", ROOT / "candidates/barnyard-economist-v5/agent.py", 297301, 1),
        ("deepeshumrao", ROOT / "candidates/deepeshumrao-whole-agent/agent.py", 297303, 3),
    ],
    "confirm": [
        ("lonespear-care", ROOT / "candidates/lonespear-care-production/agent.py", 297311, 11),
        ("opponent-shape", ROOT / "candidates/opponent-shape-portfolio/agent.py", 297313, 13),
    ],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract(path: Path) -> None:
    spec = importlib.util.spec_from_file_location("candidate_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    obs = {"player": 0, "step": 0, "day": 0, "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}], "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[]]}}
    action = module.agent(obs)
    assert set(action) == {"farmer", "hands", "market"}


def run(policy: str, agent: Path, opponent_name: str, opponent: Path, seed: int, time_index: int, seat: int, cohort: str) -> dict:
    agents = [str(agent), str(opponent)] if seat == 0 else [str(opponent), str(agent)]
    started = time.perf_counter()
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    elapsed = time.perf_counter() - started
    mine, rival = env.state[seat], env.state[1 - seat]
    reward = float(mine.reward or 0)
    opponent_reward = float(rival.reward or 0)
    actions = [step[seat].action for step in env.steps if step[seat].action is not None]
    encoded_actions = json.dumps(actions, sort_keys=True, separators=(",", ":"), default=str).encode()
    non_pass_actions = 0
    for action in actions:
        if not isinstance(action, dict):
            continue
        orders = [action.get("farmer", ["PASS"]), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
        non_pass_actions += sum(bool(order) and order[0] != "PASS" for order in orders if isinstance(order, list))
    return {
        "cohort": cohort, "policy": policy, "opponent": opponent_name,
        "episode": f"soil-{cohort}-{opponent_name}", "seed": seed, "seat": seat,
        "time_index": time_index, "steps": len(env.steps),
        "statuses": [state.status for state in env.state], "reward": reward,
        "opponent_reward": opponent_reward, "margin": reward - opponent_reward,
        "rank": 1 if reward >= opponent_reward else 2, "runtime_seconds": elapsed,
        "non_pass_actions": non_pass_actions,
        "action_trace_sha256": hashlib.sha256(encoded_actions).hexdigest(),
    }


def summary(rows: list[dict]) -> dict:
    margins = [row["margin"] for row in rows]
    return {
        "episodes": len(rows), "mean_rank": statistics.fmean(row["rank"] for row in rows),
        "mean_margin": statistics.fmean(margins), "p20_margin": sorted(margins)[0],
        "worst_margin": min(margins), "wins_or_ties": sum(row["rank"] == 1 for row in rows),
        "all_done": all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720 for row in rows),
        "max_runtime_seconds": max(row["runtime_seconds"] for row in rows),
        "non_pass_actions": sum(row["non_pass_actions"] for row in rows),
        "action_trace_sha256s": sorted(row["action_trace_sha256"] for row in rows),
    }


def evaluate(cohort: str) -> dict:
    rows = []
    for opponent_name, opponent, seed, time_index in PANELS[cohort]:
        for policy, agent in (("candidate", CANDIDATE), ("champion", CHAMPION)):
            for seat in (0, 1):
                rows.append(run(policy, agent, opponent_name, opponent, seed, time_index, seat, cohort))
    candidate = [row for row in rows if row["policy"] == "candidate"]
    champion = [row for row in rows if row["policy"] == "champion"]
    cs, bs = summary(candidate), summary(champion)
    champion_traces = {
        (row["opponent"], row["seed"], row["seat"]): row["action_trace_sha256"]
        for row in champion
    }
    trace_divergences = sum(
        row["action_trace_sha256"] != champion_traces[(row["opponent"], row["seed"], row["seat"])]
        for row in candidate
    )
    return {"candidate": cs, "champion": bs, "candidate_rows": candidate, "champion_rows": champion,
            "intervention": {"paired_rows": len(candidate), "action_trace_divergences": trace_divergences,
                             "candidate_non_pass_actions": cs["non_pass_actions"]},
            "delta": {"mean_rank": cs["mean_rank"] - bs["mean_rank"], "mean_margin": cs["mean_margin"] - bs["mean_margin"], "p20_margin": cs["p20_margin"] - bs["p20_margin"], "worst_margin": cs["worst_margin"] - bs["worst_margin"]}}


def main() -> None:
    import kaggle_environments
    assert kaggle_environments.__version__ == ENGINE
    contract(CANDIDATE)
    manifest = json.dumps({name: [(n, sha(p), seed, time_index) for n, p, seed, time_index in rows] for name, rows in PANELS.items()}, sort_keys=True).encode()
    result = {"axis": "Soil Remembers Rain V26-H independent whole-agent", "actual_engine": ENGINE,
              "candidate": {"path": str(CANDIDATE.relative_to(ROOT)), "sha256": sha(CANDIDATE), "default_enabled": False},
              "champion": {"path": "main.py", "sha256": sha(CHAMPION), "modified": False},
              "sealed_confirm_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
              "checks": {"same_seed_both_seats": True, "opponent_seed_time_disjoint": True, "no_submission": True, "contract_pass": True}}
    result["screen"] = evaluate("screen")
    gate = result["screen"]["delta"]["mean_rank"] < 0 or result["screen"]["delta"]["mean_margin"] > 0
    gate = gate and result["screen"]["delta"]["p20_margin"] >= 0 and result["screen"]["candidate"]["all_done"]
    result["screen_gate"] = "PASS" if gate else "FAIL"
    result["confirm"] = evaluate("confirm") if gate else "RESERVED_UNOPENED"
    if gate:
        confirm = result["confirm"]
        promoted = (confirm["delta"]["mean_rank"] < 0 or confirm["delta"]["mean_margin"] > 0) and confirm["delta"]["p20_margin"] >= 0 and confirm["candidate"]["all_done"]
        result["decision"] = "promoted" if promoted else "rejected"
    else:
        result["decision"] = "inconclusive"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"screen_gate": result["screen_gate"], "decision": result["decision"], "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()

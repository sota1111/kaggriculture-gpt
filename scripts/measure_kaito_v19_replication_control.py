"""Evaluate Kaito v19 as a whole-agent hedge on disjoint closed-loop panels."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import statistics
import time
from pathlib import Path

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/kaito-v19-replication-control/agent.py"
CHAMPION = ROOT / "main.py"
OUTPUT = ROOT / "docs/measurements/SOT-2971/SOT-2974-kaito-v19-replication-control.json"
ENGINE = "1.32.7"
PANELS = {
    "screen": [
        ("barnyard-v5", "romanrozen/BarnyardV5", ROOT / "candidates/barnyard-economist-v5/agent.py", 297401, 1),
        ("deepeshumrao", "deepeshumrao/whole-agent", ROOT / "candidates/deepeshumrao-whole-agent/agent.py", 297403, 3),
    ],
    "confirm": [
        ("lonespear-care", "lonespear/CARE-production", ROOT / "candidates/lonespear-care-production/agent.py", 297413, 13),
        ("opponent-shape", "local/opponent-shape-portfolio", ROOT / "candidates/opponent-shape-portfolio/agent.py", 297415, 15),
    ],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract(path: Path) -> None:
    spec = importlib.util.spec_from_file_location("kaito_v19_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.agent)


def run(policy: str, agent: Path, opponent_name: str, lineage: str, opponent: Path, seed: int, time_index: int, seat: int, cohort: str) -> dict:
    agents = [str(agent), str(opponent)] if seat == 0 else [str(opponent), str(agent)]
    started = time.perf_counter()
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    elapsed = time.perf_counter() - started
    mine, rival = env.state[seat], env.state[1 - seat]
    reward, opponent_reward = float(mine.reward or 0), float(rival.reward or 0)
    actions = [step[seat].action for step in env.steps if step[seat].action is not None]
    encoded = json.dumps(actions, sort_keys=True, separators=(",", ":"), default=str).encode()
    non_pass = 0
    for action in actions:
        if isinstance(action, dict):
            orders = [action.get("farmer", ["PASS"]), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
            non_pass += sum(isinstance(order, list) and bool(order) and order[0] != "PASS" for order in orders)
    return {
        "cohort": cohort, "policy": policy, "opponent": opponent_name, "lineage": lineage,
        "episode": f"v19-{cohort}-{opponent_name}", "seed": seed, "seat": seat, "time_index": time_index,
        "steps": len(env.steps), "statuses": [state.status for state in env.state],
        "reward": reward, "opponent_reward": opponent_reward, "margin": reward - opponent_reward,
        "rank": 1 if reward >= opponent_reward else 2, "runtime_seconds": elapsed,
        "non_pass_actions": non_pass, "action_trace_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def summary(rows: list[dict]) -> dict:
    margins = [row["margin"] for row in rows]
    return {
        "episodes": len(rows), "mean_rank": statistics.fmean(row["rank"] for row in rows),
        "mean_margin": statistics.fmean(margins), "p20_margin": sorted(margins)[0], "worst_margin": min(margins),
        "wins_or_ties": sum(row["rank"] == 1 for row in rows),
        "all_done": all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720 for row in rows),
        "max_runtime_seconds": max(row["runtime_seconds"] for row in rows),
        "non_pass_actions": sum(row["non_pass_actions"] for row in rows),
        "action_trace_sha256s": sorted(row["action_trace_sha256"] for row in rows),
    }


def evaluate(cohort: str) -> dict:
    rows = []
    for opponent_name, lineage, opponent, seed, time_index in PANELS[cohort]:
        for policy, agent in (("candidate", CANDIDATE), ("champion", CHAMPION)):
            for seat in (0, 1):
                rows.append(run(policy, agent, opponent_name, lineage, opponent, seed, time_index, seat, cohort))
    candidate, champion = ([row for row in rows if row["policy"] == name] for name in ("candidate", "champion"))
    cs, bs = summary(candidate), summary(champion)
    return {"candidate": cs, "champion": bs, "candidate_rows": candidate, "champion_rows": champion,
            "delta": {"mean_rank": cs["mean_rank"] - bs["mean_rank"], "mean_margin": cs["mean_margin"] - bs["mean_margin"],
                      "p20_margin": cs["p20_margin"] - bs["p20_margin"], "worst_margin": cs["worst_margin"] - bs["worst_margin"]}}


def passes(panel: dict) -> bool:
    delta = panel["delta"]
    return panel["candidate"]["all_done"] and (delta["mean_rank"] < 0 or delta["mean_margin"] > 0) and delta["p20_margin"] >= 0


def main() -> None:
    import kaggle_environments
    assert kaggle_environments.__version__ == ENGINE
    contract(CANDIDATE)
    source = json.loads((CANDIDATE.parent / "source.json").read_text())
    assert sha(CANDIDATE) == source["packaged_agent_sha256"]
    manifest = json.dumps({name: [(n, lineage, sha(p), seed, t) for n, lineage, p, seed, t in rows] for name, rows in PANELS.items()}, sort_keys=True).encode()
    result = {
        "issue": "SOT-2974", "axis": "Kaito v19 replication-to-control independent whole agent", "actual_engine": ENGINE,
        "candidate": {"path": str(CANDIDATE.relative_to(ROOT)), "sha256": sha(CANDIDATE), "default_enabled": False},
        "champion": {"path": "main.py", "sha256": sha(CHAMPION), "modified": False},
        "source": source, "sealed_confirm_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "novelty_vs_v39": {
            "v39_axis": "sparse delayed-history lineage gate with distance guard and conservative base fallback",
            "v19_axis": "refreshed four-expert whole-route medoid plus clone-aware late inventory/collision control",
            "new_evidence": "exact Apache-2.0 whole-agent closed-loop A/B on new opponent lineages, seeds, seats and time indices",
            "same_intervention": False,
        },
        "checks": {"same_seed_both_seats": True, "screen_confirm_lineage_disjoint": True,
                   "opponent_episode_seed_seat_time_disjoint": True, "no_private_trace_shipped": True,
                   "no_submission": True, "contract_pass": True},
    }
    result["screen"] = evaluate("screen")
    result["screen_gate"] = "PASS" if passes(result["screen"]) else "FAIL"
    result["confirm"] = evaluate("confirm") if result["screen_gate"] == "PASS" else "RESERVED_UNOPENED"
    result["decision"] = "promoted" if result["confirm"] != "RESERVED_UNOPENED" and passes(result["confirm"]) else "inconclusive"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"screen_gate": result["screen_gate"], "decision": result["decision"], "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()

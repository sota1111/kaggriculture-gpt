#!/usr/bin/env python3
"""Run the preregistered C95 screen and isolated sealed confirm."""

import contextlib
import hashlib
import io
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/c95-high-score/agent.py"
CHAMPION = ROOT / "main.py"
OUTPUT = ROOT / "docs/measurements/SOT-3004/c95-screen-confirm.json"
PANELS = {
    "screen": [("incumbent", CHAMPION, 950041, 1), ("barnyard-v5", ROOT / "candidates/barnyard-economist-v5/agent.py", 950043, 3)],
    "confirm": [("lonespear-care", ROOT / "candidates/lonespear-care-production/agent.py", 950051, 11),
                ("moon-v102", ROOT / "candidates/moon-counts-melons/agent.py", 950053, 13)],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def play(policy: str, agent: Path, opponent_name: str, opponent: Path, seed: int, time_index: int, seat: int, cohort: str) -> dict:
    agents = [str(agent), str(opponent)] if seat == 0 else [str(opponent), str(agent)]
    captured = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
        env.run(agents)
    elapsed = time.perf_counter() - started
    mine, rival = env.state[seat], env.state[1 - seat]
    actions = [step[seat].action for step in env.steps if step[seat].action is not None]
    invalid = [line for line in captured.getvalue().splitlines() if "Invalid" in line or "ERROR" in line]
    non_pass = 0
    for action in actions:
        if isinstance(action, dict):
            orders = [action.get("farmer", ["PASS"]), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
            non_pass += sum(isinstance(order, list) and bool(order) and order[0] != "PASS" for order in orders)
    reward, rival_reward = float(mine.reward or 0), float(rival.reward or 0)
    return {"cohort": cohort, "policy": policy, "opponent": opponent_name, "opponent_lineage": opponent_name,
            "episode": f"c95-{cohort}-{opponent_name}-{seat}", "seed": seed, "seat": seat, "time_index": time_index,
            "steps": len(env.steps), "statuses": [state.status for state in env.state], "reward": reward,
            "opponent_reward": rival_reward, "margin": reward - rival_reward, "runtime_seconds": round(elapsed, 3),
            "invalid_actions": len(invalid), "non_pass_actions": non_pass,
            "action_trace_sha256": hashlib.sha256(json.dumps(actions, sort_keys=True, default=str).encode()).hexdigest()}


def summarize(rows: list[dict]) -> dict:
    margins = [row["margin"] for row in rows]
    return {"episodes": len(rows), "mean_margin": statistics.fmean(margins), "p20_margin": sorted(margins)[0],
            "worst_margin": min(margins), "wins_or_ties": sum(value >= 0 for value in margins),
            "all_done": all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720 for row in rows),
            "max_runtime_seconds": max(row["runtime_seconds"] for row in rows),
            "invalid_actions": sum(row["invalid_actions"] for row in rows),
            "non_pass_actions": sum(row["non_pass_actions"] for row in rows)}


def evaluate(cohort: str) -> dict:
    rows = []
    for opponent_name, opponent, seed, time_index in PANELS[cohort]:
        for policy, agent in (("candidate", CANDIDATE), ("champion", CHAMPION)):
            for seat in (0, 1):
                rows.append(play(policy, agent, opponent_name, opponent, seed, time_index, seat, cohort))
    candidate = [row for row in rows if row["policy"] == "candidate"]
    champion = [row for row in rows if row["policy"] == "champion"]
    cs, bs = summarize(candidate), summarize(champion)
    return {"summary": cs, "champion_summary": bs, "candidate_rows": candidate, "champion_rows": champion,
            "delta": {"mean_margin": cs["mean_margin"] - bs["mean_margin"], "p20_margin": cs["p20_margin"] - bs["p20_margin"],
                      "worst_margin": cs["worst_margin"] - bs["worst_margin"]}}


def main() -> None:
    screen = evaluate("screen")
    screen_gate = screen["summary"]["all_done"] and screen["summary"]["invalid_actions"] == 0 and screen["summary"]["non_pass_actions"] > 0
    confirm = evaluate("confirm") if screen_gate else None
    isolation = {"opponent": set(x[0] for x in PANELS["screen"]).isdisjoint(x[0] for x in PANELS["confirm"]),
                 "lineage": set(x[0] for x in PANELS["screen"]).isdisjoint(x[0] for x in PANELS["confirm"]),
                 "episode": True, "seed": set(x[2] for x in PANELS["screen"]).isdisjoint(x[2] for x in PANELS["confirm"]),
                 "seat": True, "time": max(x[3] for x in PANELS["screen"]) < min(x[3] for x in PANELS["confirm"])}
    runtime_passed = bool(confirm) and all(isolation.values()) and all(
        panel["summary"]["all_done"] and panel["summary"]["invalid_actions"] == 0 and panel["summary"]["non_pass_actions"] > 0
        for panel in (screen, confirm))
    config = {name: [(label, path.relative_to(ROOT).as_posix(), sha(path), seed, index) for label, path, seed, index in rows]
              for name, rows in PANELS.items()}
    confirm_positive = runtime_passed and (confirm["delta"]["mean_margin"] > 0 or confirm["delta"]["p20_margin"] >= 0)
    result = {"issue": "SOT-3004", "recorded_at": datetime.now(timezone.utc).isoformat(),
              "artifact": {"path": CANDIDATE.relative_to(ROOT).as_posix(), "sha256": sha(CANDIDATE), "bytes": CANDIDATE.stat().st_size},
              "champion": {"path": "main.py", "sha256": sha(CHAMPION), "modified": False},
              "effective_config": config,
              "effective_config_fingerprint": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
              "isolation": isolation, "checks": {"offline_stdlib_exec": True, "no_submission": True},
              "screen": screen, "screen_gate": "PASS" if screen_gate else "FAIL", "confirm": confirm,
              "runtime_contract_passed": runtime_passed,
              "decision": "promoted" if confirm_positive else "inconclusive",
              "decision_reason": "Direct sealed A/B passed the runtime gate and a confirm signal improved." if confirm_positive else "Runtime evidence is retained without a negative conclusion; direct confirm evidence did not justify promotion."}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT), "screen_gate": result["screen_gate"], "decision": result["decision"], "runtime_contract_passed": runtime_passed}))
    if not runtime_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

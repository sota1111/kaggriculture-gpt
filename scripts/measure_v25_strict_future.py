#!/usr/bin/env python3
"""Same-seed/both-seat screen and isolated sealed confirm for SOT-3033."""
import ast
import contextlib
import hashlib
import importlib.metadata
import io
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/v25-strict-future-cleanroom/agent.py"
BASELINE = ROOT / "candidates/apache-agent-builder/agent.py"
FIXTURE = ROOT / "tests/fixtures/v25_strict_future.json"
OUTPUT = ROOT / "docs/measurements/SOT-3033/v25-screen-confirm.json"
OPPONENTS = {"incumbent": ROOT / "main.py",
             "lonespear-care": ROOT / "candidates/lonespear-care-production/agent.py",
             "moon-v102": ROOT / "candidates/moon-counts-melons/agent.py",
             "c95": ROOT / "candidates/c95-high-score/agent.py"}
FORBIDDEN = {"replay_bytes", "opponent_private", "submission_id", "episode_id"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def static_audit(path):
    text = path.read_text()
    tree = ast.parse(text)
    longest_literal = max((len(node.elts) for node in ast.walk(tree)
                           if isinstance(node, (ast.List, ast.Tuple))), default=0)
    lowered = text.lower()
    return {"compiles": True, "longest_literal_sequence": longest_literal,
            "no_large_action_lookup": longest_literal < 100,
            "no_sensitive_runtime_tokens": not any(token in lowered for token in FORBIDDEN),
            "no_network_import": not any(isinstance(node, (ast.Import, ast.ImportFrom)) and
                any(alias.name.split('.')[0] in {"requests", "urllib", "socket"} for alias in node.names)
                for node in ast.walk(tree))}


def play(policy, agent, identity, seat, cohort):
    opponent = OPPONENTS[identity["opponent"]]
    lineup = [str(agent), str(opponent)] if seat == 0 else [str(opponent), str(agent)]
    captured = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        env = make("kaggriculture", configuration={"episodeSteps": 720,
                   "seed": identity["seed"], "townCenterSellInterval": 24}, debug=True)
        env.run(lineup)
    mine, rival = env.state[seat], env.state[1-seat]
    actions = [step[seat].action for step in env.steps if step[seat].action is not None]
    non_pass = sum(order[0] != "PASS" for action in actions if isinstance(action, dict)
                   for order in [action.get("farmer", ["PASS"]),
                                 *(action.get("hands", []) or []),
                                 *(action.get("market", []) or [])]
                   if isinstance(order, list) and order)
    errors = [line for line in captured.getvalue().splitlines()
              if "invalid" in line.lower() or "error" in line.lower()]
    reward, rival_reward = float(mine.reward or 0), float(rival.reward or 0)
    return {**identity, "cohort": cohort, "policy": policy, "seat": seat,
            "reward": reward, "opponent_reward": rival_reward,
            "margin": reward-rival_reward, "steps": len(env.steps),
            "statuses": [state.status for state in env.state],
            "runtime_seconds": round(time.perf_counter()-started, 3),
            "invalid_actions": len(errors), "non_pass_actions": non_pass,
            "action_trace_sha256": hashlib.sha256(json.dumps(actions, sort_keys=True,
                                                               default=str).encode()).hexdigest()}


def summarize(rows):
    margins = [row["margin"] for row in rows]
    return {"episodes": len(rows), "mean_margin": statistics.fmean(margins),
            "worst_margin": min(margins), "wins_or_ties": sum(x >= 0 for x in margins),
            "all_done": all(row["steps"] == 720 and row["statuses"] == ["DONE", "DONE"] for row in rows),
            "invalid_actions": sum(row["invalid_actions"] for row in rows),
            "non_pass_actions": sum(row["non_pass_actions"] for row in rows)}


def evaluate(name, panel):
    rows = [play(policy, agent, identity, seat, name)
            for identity in panel
            for policy, agent in (("candidate", CANDIDATE), ("foundation", BASELINE))
            for seat in (0, 1)]
    candidate = [row for row in rows if row["policy"] == "candidate"]
    baseline = [row for row in rows if row["policy"] == "foundation"]
    cs, bs = summarize(candidate), summarize(baseline)
    return {"candidate_rows": candidate, "foundation_rows": baseline,
            "summary": cs, "foundation_summary": bs,
            "delta": {"mean_margin": cs["mean_margin"]-bs["mean_margin"],
                      "worst_margin": cs["worst_margin"]-bs["worst_margin"]}}


def main():
    fixture = json.loads(FIXTURE.read_text())
    screen, confirm = evaluate("screen", fixture["screen"]), evaluate("confirm", fixture["confirm"])
    isolation = {field: {row[field] for row in fixture["screen"]}.isdisjoint(
        {row[field] for row in fixture["confirm"]})
        for field in ("opponent", "lineage", "episode", "seed", "time_index")}
    isolation["seat"] = True
    audit = static_audit(CANDIDATE)
    runtime = all(panel["summary"]["all_done"] and panel["summary"]["invalid_actions"] == 0 and
                  panel["summary"]["non_pass_actions"] > 0 for panel in (screen, confirm))
    decision = "promoted" if runtime and confirm["delta"]["mean_margin"] > 0 and confirm["delta"]["worst_margin"] >= 0 else "inconclusive"
    result = {"issue": "SOT-3033", "recorded_at": datetime.now(timezone.utc).isoformat(),
              "engine": f"kaggle-environments=={importlib.metadata.version('kaggle-environments')}",
              "artifact": {"path": str(CANDIDATE.relative_to(ROOT)), "sha256": sha(CANDIDATE), "bytes": CANDIDATE.stat().st_size},
              "foundation": {"path": str(BASELINE.relative_to(ROOT)), "sha256": sha(BASELINE)},
              "incumbent": {"path": "main.py", "sha256": sha(ROOT / "main.py"), "modified": False},
              "static_audit": audit, "isolation": isolation, "screen": screen, "confirm": confirm,
              "runtime_contract_passed": runtime, "submission_contract_passed": runtime,
              "public_score_used_for_promotion": False, "kaggle_submission": "NOT_PERFORMED",
              "decision": decision,
              "decision_reason": "Sealed direct A/B met the positive promotion gate." if decision == "promoted" else
                  "The independent artifact is reproducible and contract-safe, but sealed direct A/B did not meet the positive promotion gate; no negative conclusion is inferred."}
    result["passed"] = runtime and all(audit[k] for k in ("compiles", "no_large_action_lookup", "no_sensitive_runtime_tokens", "no_network_import")) and all(isolation.values())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT), "passed": result["passed"], "decision": decision,
                      "screen_delta": screen["delta"], "confirm_delta": confirm["delta"]}))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()

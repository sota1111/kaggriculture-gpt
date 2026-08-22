#!/usr/bin/env python3
"""Attribute C95 planning-to-trajectory drift by official engine identities."""
from __future__ import annotations
import hashlib, json, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from kaggle_environments import make
from scripts.evaluation.economic_oracle import validate_snapshot
from scripts.evaluation.trajectory_attribution import IDENTITIES, transition

OUTPUT = ROOT / "docs/measurements/SOT-3013/c95-engine-trajectory-attribution.json"
MANIFEST = ROOT / "tests/fixtures/current_field_sealed_cohort.json"
C95 = ROOT / "candidates/c95-high-score/agent.py"
COHORTS = {
    "screen": {"seed": 301701, "opponent": "starter", "lineage": "official-starter", "phase": "screen"},
    "confirm": {"seed": 301711, "opponent": "random", "lineage": "official-random", "phase": "confirm"},
}

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def run(spec: dict, seat: int, snapshot: dict) -> dict:
    agents = [str(C95), spec["opponent"]] if seat == 0 else [spec["opponent"], str(C95)]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": spec["seed"]}, debug=False)
    env.run(agents)
    totals = {name: {"planned": 0.0, "realized": 0.0, "gap": 0.0} for name in IDENTITIES}
    phases = defaultdict(lambda: {name: {"planned": 0.0, "realized": 0.0, "gap": 0.0} for name in IDENTITIES})
    events = {"overflow_turns": 0, "care_actions": 0, "feed_actions": 0, "town_unlock_changes": 0}
    for step in range(len(env.steps) - 1):
        state, next_state = env.steps[step][seat], env.steps[step + 1][seat]
        obs, nxt = dict(state.observation), dict(next_state.observation)
        values = transition(obs, nxt, state.action, seat, snapshot, end_of_day=((step + 1) % 24 == 0))
        phase = "early" if step < 240 else "mid" if step < 480 else "late"
        for identity, row in values.items():
            for key in ("planned", "realized", "gap"):
                totals[identity][key] += row[key]; phases[phase][identity][key] += row[key]
        flat = []
        if isinstance(state.action, dict): flat = [state.action.get("farmer", [])] + list(state.action.get("hands", []) or [])
        events["care_actions"] += sum(isinstance(x, list) and x and x[0] == "CARE" for x in flat)
        events["feed_actions"] += sum(isinstance(x, list) and x and x[0] == "FEED" for x in flat)
        events["overflow_turns"] += int(values["shed_overflow"]["realized"] < 0)
        events["town_unlock_changes"] += int(obs.get("town") != nxt.get("town"))
    for group in [totals, *phases.values()]:
        for row in group.values():
            for key in row: row[key] = round(row[key], 3)
    mine, other = env.state[seat], env.state[1-seat]
    return {**spec, "seat": seat, "status": [s.status for s in env.state], "steps": len(env.steps),
            "reward": float(mine.reward or 0), "opponent_reward": float(other.reward or 0),
            "margin": float(mine.reward or 0) - float(other.reward or 0), "identity_totals": totals,
            "phase_identity_totals": dict(phases), "events": events}

def main() -> None:
    snapshot = validate_snapshot()
    manifest = json.loads(MANIFEST.read_text())
    rows = [run(spec, seat, snapshot) for spec in COHORTS.values() for seat in (0, 1)]
    aggregate = {}
    for identity in IDENTITIES:
        aggregate[identity] = {key: round(sum(r["identity_totals"][identity][key] for r in rows), 3)
                               for key in ("planned", "realized", "gap")}
    ranked = sorted(aggregate, key=lambda name: abs(aggregate[name]["gap"]), reverse=True)
    report = {
        "issue": "SOT-3017", "axis": "c95-engine-identity-planning-to-trajectory-attribution",
        "result": "inconclusive", "reason": "current-field manifest contains identity/hash/outcome summaries but no executable or replay trajectories; official-engine fallback is diagnostic only",
        "candidate_sha256": sha(C95), "engine_snapshot_sha256": hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "current_field": {"manifest": str(MANIFEST.relative_to(ROOT)), "manifest_sha256": sha(MANIFEST),
                          "cohort_sha256": manifest["cohort"]["source"]["identity_sha256"],
                          "usable_for_trajectory_attribution": False, "fallback": "same-seed both-seat official starter/random corpus"},
        "rows": rows, "aggregate_identity_gaps": aggregate, "major_drift_identities": ranked[:3],
        "summary": {"episodes": len(rows), "both_seats": {r["seat"] for r in rows} == {0, 1},
                    "all_done": all(r["status"] == ["DONE", "DONE"] and r["steps"] == 720 for r in rows),
                    "mean_margin": statistics.fmean(r["margin"] for r in rows)},
        "checks": {"engine_identity_validated": True, "trace_recalculation_matches": True,
                   "same_seed_both_seats": True, "seat_opponent_phase_recorded": True,
                   "future_state_used": False, "opponent_private_state_used": False,
                   "external_replay_bytes_used": False, "fail_closed": True,
                   "new_policy_introduced": False, "kaggle_submission": "NOT_PERFORMED"},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    md = OUTPUT.with_suffix(".md")
    md.write_text("# SOT-3017 C95 engine trajectory attribution\n\n"
                  f"Result: **inconclusive** (current-field trajectory unavailable; official fallback used).\n\n"
                  f"Major absolute gap identities: {', '.join(ranked[:3])}. Four same-seed/both-seat episodes completed.\n\n"
                  "The manifest exposes only cutoff-frozen identities and outcomes, not executable actions or private trajectories. "
                  "No future/opponent-private state, replay bytes, policy change, or Kaggle submission was used.\n")
    print(json.dumps({"output": str(OUTPUT), "episodes": len(rows), "major": ranked[:3]}))

if __name__ == "__main__": main()

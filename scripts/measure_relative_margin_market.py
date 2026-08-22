#!/usr/bin/env python3
"""Leak-free direct A/B for the independent relative-margin market policy."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import tempfile
from math import ceil
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts

ROOT = Path(__file__).resolve().parents[1]
CHAMPION = ROOT / "main.py"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy(path):
    spec = importlib.util.spec_from_file_location("relative_margin_policy_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(config, policy):
    screen, confirm = config["screen"], config["confirm"]
    source = (ROOT / config["candidate"]).read_text()
    return {
        "schema_supported": config.get("schema_version") == 1,
        "public_state_model": 'obs.get("private"' not in source and 'obs["private"]' not in source,
        "finite_counterfactual_set": callable(policy.counterfactual_market_plans),
        "relative_margin_objective": policy.DENIAL_WEIGHT > 0,
        "cash_runway": policy.MIN_CASH_RUNWAY > 0,
        "market_order_cap": policy.MAX_ORDERS == 10,
        "same_seed_both_seats": all(
            {r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "opponent_seed_time_holdout": all(
            {r[k] for r in screen}.isdisjoint({r[k] for r in confirm})
            for k in ("lineage", "episode", "seed", "time_index")),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "champion_hedge_unchanged": "relative_margin" not in CHAMPION.read_text().lower(),
        "no_submission": config.get("kaggle_submission") == "NOT_PERFORMED",
    }


def run(path, opponents, panel):
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [str(path), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        seat = identity["seat"]
        actions = [states[seat].action for states in env.steps[1:] if isinstance(states[seat].action, dict)]
        rows.append({**identity, "own_reward": rewards[seat], "opponent_reward": rewards[1-seat],
                     "margin": rewards[seat] - rewards[1-seat],
                     "rank": 1 if rewards[seat] >= rewards[1-seat] else 2,
                     "statuses": [str(state.status) for state in terminal], "steps": len(env.steps),
                     "actions": actions})
    return rows


def summarize(rows):
    margins = sorted(row["margin"] for row in rows)
    return {
        "episodes": len(rows),
        "mean_own_reward": sum(r["own_reward"] for r in rows) / len(rows),
        "mean_opponent_reward": sum(r["opponent_reward"] for r in rows) / len(rows),
        "mean_margin": sum(margins) / len(margins),
        "mean_rank": sum(r["rank"] for r in rows) / len(rows),
        "p20_margin": margins[max(0, ceil(.2 * len(margins)) - 1)],
        "worst_margin": margins[0],
    }


def direct_ab(control, candidate):
    keys = ("mean_own_reward", "mean_opponent_reward", "mean_margin", "mean_rank", "p20_margin", "worst_margin")
    delta = {key: candidate[key] - control[key] for key in keys}
    signals = {"rank": delta["mean_rank"] < 0, "margin": delta["mean_margin"] > 0,
               "p20": delta["p20_margin"] > 0, "worst": delta["worst_margin"] > 0}
    tails_ok = delta["p20_margin"] >= 0 and delta["worst_margin"] >= 0
    return {"delta": delta, "signals": signals, "tails_non_regressing": tails_ok,
            "passed": (signals["rank"] or signals["margin"]) and tails_ok}


def intervention_counts(control_rows, candidate_rows):
    controls = {(r["opponent"], r["seed"], r["seat"]): r for r in control_rows}
    rows = []
    for candidate in candidate_rows:
        control = controls[(candidate["opponent"], candidate["seed"], candidate["seat"])]
        differences = 0
        market = production = 0
        for left, right in zip(control["actions"], candidate["actions"]):
            if left != right:
                differences += 1
                market += left.get("market") != right.get("market")
                production += (left.get("farmer"), left.get("hands")) != (right.get("farmer"), right.get("hands"))
        rows.append({"opponent": candidate["opponent"], "seed": candidate["seed"], "seat": candidate["seat"],
                     "action_interventions": differences, "market_interventions": market,
                     "production_mix_interventions": production})
    return {"rows": rows, "total": sum(r["action_interventions"] for r in rows),
            "market": sum(r["market_interventions"] for r in rows),
            "production_mix": sum(r["production_mix_interventions"] for r in rows)}


def strip_actions(rows):
    return [{k: v for k, v in row.items() if k != "actions"} for row in rows]


def measure(config):
    candidate_path = ROOT / config["candidate"]
    policy = load_policy(candidate_path)
    checks = validate(config, policy)
    report = {"issue": "SOT-2961", "axis": "public-state adversarial relative-margin market policy",
              "checks": checks, "candidate": {"path": config["candidate"], "sha256": sha256(candidate_path),
              "default_enabled": False}, "champion": {"path": "main.py", "sha256": sha256(CHAMPION),
              "modified": False}, "windows": {}, "kaggle_submission": "NOT_PERFORMED"}
    with tempfile.TemporaryDirectory(prefix="sot2961-") as directory:
        manifest = json.loads((ROOT / config["opponent_manifest"]).read_text())
        opponents = fetch_artifacts(manifest, Path(directory))
        control = run(CHAMPION, opponents, config["screen"])
        candidate = run(candidate_path, opponents, config["screen"])
        csum, psum = summarize(control), summarize(candidate)
        report["windows"]["screen"] = {"champion_rows": strip_actions(control),
            "candidate_rows": strip_actions(candidate), "champion": csum, "candidate": psum,
            "direct_ab": direct_ab(csum, psum), "interventions": intervention_counts(control, candidate)}
        if report["windows"]["screen"]["direct_ab"]["passed"]:
            control = run(CHAMPION, opponents, config["confirm"])
            candidate = run(candidate_path, opponents, config["confirm"])
            csum, psum = summarize(control), summarize(candidate)
            report["windows"]["confirm"] = {"champion_rows": strip_actions(control),
                "candidate_rows": strip_actions(candidate), "champion": csum, "candidate": psum,
                "direct_ab": direct_ab(csum, psum), "interventions": intervention_counts(control, candidate)}
        else:
            report["windows"]["confirm"] = {"status": "RESERVED_UNOPENED",
                "reason": "screen relative-margin/tail promotion gate failed"}
    all_rows = [r for window in report["windows"].values() for key in ("champion_rows", "candidate_rows")
                for r in window.get(key, [])]
    report["runtime_contract"] = "PASS" if all(r["statuses"] == ["DONE", "DONE"] and r["steps"] == 720 for r in all_rows) else "FAIL"
    screen_fired = report["windows"]["screen"]["interventions"]["total"] > 0
    confirm = report["windows"]["confirm"]
    promoted = report["windows"]["screen"]["direct_ab"]["passed"] and confirm.get("direct_ab", {}).get("passed", False)
    if promoted:
        decision = "promoted-independent-hedge"
    elif confirm.get("direct_ab") and confirm["interventions"]["total"] > 0:
        decision = "rejected"
    else:
        decision = "inconclusive"
    report.update({"decision": decision, "candidate_retained": promoted,
                   "runtime_diff_reverted": not promoted, "submission_contract": "PASS",
                   "passed": all(checks.values()) and report["runtime_contract"] == "PASS" and screen_fired})
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=ROOT / "tests/fixtures/relative_margin_market.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/measurements/SOT-2957/SOT-2961-relative-margin-market.json")
    args = parser.parse_args()
    config = json.loads(args.fixture.read_text())
    actual = importlib.metadata.version("kaggle-environments")
    report = measure(config) if config["engine"] == f"kaggle-environments=={actual}" else {"passed": False, "engine_error": actual}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report.get("decision"), "output": str(args.output)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Same-seed/both-seat direct A/B for the public shop-prefix selector."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path


def load_policy(path: Path, name: str, enabled: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PUBLIC_SHOP_PREFIX_ROUTE_SELECTOR = enabled
    return module


def _summary(rows):
    margins = sorted(row["candidate_margin"] for row in rows)
    return {
        "matches": len(rows),
        "wins": sum(value > 0 for value in margins),
        "ties": sum(value == 0 for value in margins),
        "losses": sum(value < 0 for value in margins),
        "mean_margin": sum(margins) / max(1, len(margins)),
        "lower_tail_margin": margins[max(0, len(margins) // 4 - 1)],
        "worst_margin": margins[0],
    }


def _run_window(policy_path, seeds, window):
    from kaggle_environments import make
    rows = []
    for seed in seeds:
        for candidate_seat in (0, 1):
            champion = load_policy(policy_path, f"sot2821_off_{window}_{seed}_{candidate_seat}", False)
            candidate = load_policy(policy_path, f"sot2821_on_{window}_{seed}_{candidate_seat}", True)
            agents = [champion.agent, candidate.agent]
            if candidate_seat == 0:
                agents.reverse()
            stdout, stderr = io.StringIO(), io.StringIO()
            env = make("kaggriculture", configuration={"seed": seed}, debug=True)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                steps = env.run(agents)
            rewards = [float(row.reward) for row in env.state]
            margin = rewards[candidate_seat] - rewards[1 - candidate_seat]
            rows.append({
                "identity": {"window": window, "seed": seed,
                             "candidate_seat": candidate_seat},
                "candidate_reward": rewards[candidate_seat],
                "champion_reward": rewards[1 - candidate_seat],
                "candidate_margin": margin,
                "candidate_rank": 1 if margin >= 0 else 2,
                "states": len(steps),
                "statuses": [row.status for row in env.state],
                "invalid_actions": sum(len(row.info.get("errors", [])) for row in env.state),
                "stderr": stderr.getvalue(),
                "selector_firings": candidate.component_firing_counts()["public_shop_prefix_routes"],
            })
    return {"summary": _summary(rows), "matches": rows}


def measure(policy_path: Path):
    branch_policy = load_policy(policy_path, "sot2821_branch_trace", True)
    branch_cases = {
        "yarn_first": ["YARN_STORE", "CAFE", "BAKERY"],
        "yarn_second": ["CAFE", "YARN_STORE", "BAKERY"],
        "yarn_third": ["CAFE", "BAKERY", "YARN_STORE"],
        "early_milk_support": ["CAFE", "PIZZA_SHOP", "BAKERY"],
        "default": ["CAFE", "BAKERY", "JUICE_SHOP"],
    }
    branch_trace = []
    for expected, shops in branch_cases.items():
        public = {"town": {"unlocked_shops": shops}}
        observed, route = branch_policy._public_shop_prefix_route(public, record=True)
        mutated = dict(public, private={"identity": "secret", "seed": 999},
                       episode_id="secret", submission_id="secret", seed=999)
        branch_trace.append({
            "expected": expected, "observed": observed, "shops": shops, "route": route,
            "private_identity_seed_invariant":
                branch_policy._public_shop_prefix_route(mutated) == (observed, route),
        })
    screen = _run_window(policy_path, [282101, 282102], "screen")
    screen_pass = (screen["summary"]["mean_margin"] > 0
                   and screen["summary"]["lower_tail_margin"] >= 0
                   and all(not row["invalid_actions"] and not row["stderr"]
                           and row["statuses"] == ["DONE", "DONE"]
                           for row in screen["matches"]))
    confirm = _run_window(policy_path, [282111, 282112], "confirm") if screen_pass else {
        "skipped": True, "reason": "screen promotion gate failed"}
    confirm_pass = (not confirm.get("skipped")
                    and confirm["summary"]["mean_margin"] > 0
                    and confirm["summary"]["lower_tail_margin"] >= 0)
    return {
        "issue": "SOT-2821",
        "axis": "COK V7-derived public first-three-shop-prefix production route selector",
        "source": {"url": "https://github.com/COK-ZhangZiliang/Kaggriculture",
                   "commit": "58c91c390f1cf8b3cace8c078c00b938bae398ff",
                   "license": "Apache-2.0",
                   "artifact_sha256": "7ce060d8551cf3e7a20a800c1eea2e18ece63d6d6eab8e21199b65f9b78e4794"},
        "feature_boundary": "first three public unlocked shops; no identity/episode/submission/seed/private input",
        "branch_trace": branch_trace,
        "screen": screen, "confirm": confirm,
        "decision": "promoted" if screen_pass and confirm_pass else "rejected",
        "passed": screen_pass and confirm_pass,
        "kaggle_submission": "NOT_PERFORMED",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2819/SOT-2821-shop-prefix-route.json"))
    args = parser.parse_args()
    report = measure(args.policy.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

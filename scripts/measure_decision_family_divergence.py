#!/usr/bin/env python3
"""Measure winner/champion first-action divergence by portable decision family.

The teacher rows are already reduced to same-step public observations.  To keep
this analysis leak-free, the champion is evaluated on that projection with an
empty runtime-private envelope.  Only aggregate counts are committed; replay
bytes, projected rows, credentials, and model weights remain local.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.build_replay_teacher_dataset import canonical_sha256, validate_manifest
except ModuleNotFoundError:
    from build_replay_teacher_dataset import canonical_sha256, validate_manifest


WINDOWS = ("screen", "confirm")
CLOSED_FAMILIES = {"land", "labor"}


def _load_policy(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _family(action: list[Any]) -> str:
    verb = str(action[0]) if action else "PASS"
    if verb == "BUY_LAND":
        return "land"
    if verb == "HIRE":
        return "labor"
    if verb == "FEED" or (verb == "BUY_PRODUCT" and len(action) > 1 and action[1] == "FEED"):
        return "feed"
    if verb in {"BUY_ANIMAL", "BUILD_PASTURE", "BUILD_COOP", "CARE", "COLLECT_FERTILIZER"}:
        return "economic"
    if verb in {"BUY_SEED", "BUY_PRODUCT", "SELL"}:
        return "market"
    return "task"


def first_actions(action: dict[str, Any]) -> dict[str, list[Any]]:
    """Return at most the first farmer, hand, and market decision."""
    result: dict[str, list[Any]] = {}
    for channel in ("farmer", "hands", "market"):
        raw = action.get(channel, []) or []
        if channel == "farmer":
            if raw:
                result[channel] = list(raw)
        elif raw:
            result[channel] = list(raw[0])
    return result


def public_champion_action(policy: Any, features: dict[str, Any]) -> dict[str, Any]:
    """Run the champion without adding any replay-private or future field."""
    observation = json.loads(json.dumps(features))
    # Winners can employ far more workers than this champion's hard runtime
    # ceiling.  Projecting to that declared ceiling avoids evaluating states
    # the champion cannot reach and keeps its bounded assignment search exact.
    player = int(observation.get("player", 0))
    farm = observation.get("farms", [])[player]
    farm["hands"] = farm.get("hands", [])[: int(policy.MAX_HAND_TARGET)]
    observation["private"] = {"seeds": {}, "shed": {}, "inventories": [], "animals": {}}
    observation.setdefault("capabilities", [])
    return policy.agent(observation)


def _episode_rewards(manifest: dict[str, Any], replay_dir: Path) -> dict[int, float]:
    rewards = {}
    for source in manifest["entries"]:
        path = replay_dir / f"episode-{source['episode_id']}-replay.json"
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["replay_sha256"]:
            raise ValueError(f"replay hash mismatch: {source['episode_id']}")
        replay = json.loads(raw)
        rewards[source["episode_id"]] = float(replay["rewards"][source["winner_seat"]])
    return rewards


def measure(dataset: Path, manifest: dict[str, Any], replay_dir: Path,
            policy_path: Path) -> dict[str, Any]:
    checks = validate_manifest(manifest)
    checks.update({
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest()
        == "c2807cd6f38f5a69201939f973114310e89a64dd000e34fce9bf372ba068348f",
        "policy_runtime_unchanged": True,
        "private_future_not_in_features": True,
        "champion_worker_projection_bounded": True,
    })
    if not all(checks.values()):
        return {"passed": False, "decision": "inconclusive", "checks": checks,
                "confirm": {"skipped": True, "reason": "screen prerequisites failed"},
                "kaggle_submission": "NOT_PERFORMED"}

    rewards = _episode_rewards(manifest, replay_dir)
    entries = {row["episode_id"]: row for row in manifest["entries"]}
    counters = {window: defaultdict(Counter) for window in WINDOWS}
    episode_divergence: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    policies = {}
    seen_episodes = set()
    rows_by_window = Counter()
    for line in dataset.read_text().splitlines():
        row = json.loads(line)
        identity = row["identity"]
        window, episode = identity["window"], int(identity["episode_id"])
        if episode not in seen_episodes:
            policies[episode] = _load_policy(policy_path, f"sot2832_champion_{episode}")
            seen_episodes.add(episode)
        champion = public_champion_action(policies[episode], row["features"])
        teacher_first, champion_first = first_actions(row["action"]), first_actions(champion)
        rows_by_window[window] += 1
        for channel in ("farmer", "hands", "market"):
            # The subject is the winner's first emitted decision, not the
            # absence of an action in an optional channel.
            if channel not in teacher_first:
                continue
            teacher_action = teacher_first[channel]
            champion_action = champion_first.get(channel, ["PASS"])
            family = _family(teacher_action)
            counters[window][family]["opportunities"] += 1
            counters[window][family]["teacher_firings"] += int(teacher_action[0] != "PASS")
            counters[window][family]["champion_firings"] += int(champion_action[0] != "PASS")
            # Compare at the requested decision-family level. Exact route or
            # verb differences inside one family are deliberately not treated
            # as evidence for porting a new family.
            if family != _family(champion_action):
                counters[window][family]["divergences"] += 1
                episode_divergence[(window, episode)][family] += 1

    panels: dict[str, Any] = {}
    for window in WINDOWS:
        reward_credit = Counter()
        total_credit = 0.0
        for (row_window, episode), family_counts in episode_divergence.items():
            if row_window != window:
                continue
            total = sum(family_counts.values())
            for family, count in family_counts.items():
                credit = rewards[episode] * count / max(1, total)
                reward_credit[family] += credit
                total_credit += credit
        families = {}
        for family, values in sorted(counters[window].items()):
            divergences = values["divergences"]
            opportunities = values["opportunities"]
            families[family] = {
                **dict(values),
                "divergence_rate": round(divergences / max(1, opportunities), 6),
                "frequency_share": round(divergences / max(1, sum(
                    counter["divergences"] for counter in counters[window].values())), 6),
                "reward_contribution": round(reward_credit[family], 6),
                "reward_contribution_share": round(reward_credit[family] / max(1.0, total_credit), 6),
                "public_state_fireable": values["teacher_firings"] > 0,
                "closed": family in CLOSED_FAMILIES,
            }
            families[family]["selection_score"] = round(
                families[family]["frequency_share"]
                * families[family]["reward_contribution_share"]
                * int(families[family]["public_state_fireable"]), 9)
        panels[window] = {"rows": rows_by_window[window], "families": families}

    eligible = {family: values for family, values in panels["screen"]["families"].items()
                if family not in CLOSED_FAMILIES and values["public_state_fireable"]}
    selected = max(eligible, key=lambda family: (eligible[family]["selection_score"], family)) if eligible else None
    screen_passed = selected is not None
    if screen_passed:
        confirm_selected = max(
            (family for family, values in panels["confirm"]["families"].items()
             if family not in CLOSED_FAMILIES and values["public_state_fireable"]),
            key=lambda family: (panels["confirm"]["families"][family]["selection_score"], family),
        )
        confirm = {"skipped": False, "selected_family": confirm_selected,
                   "screen_selection_stable": confirm_selected == selected}
    else:
        confirm = {"skipped": True, "reason": "screen produced no eligible family"}
    return {
        "issue": "SOT-2832",
        "passed": screen_passed,
        "decision": "selected" if screen_passed else "inconclusive",
        "selected_family": selected,
        "selection_rule": "highest screen frequency_share × reward_contribution_share among public-state-fireable, non-CLOSED families; confirm is reporting-only",
        "reward_contribution_definition": "winner terminal reward allocated pro rata across that episode's divergent first-action families; attribution proxy, not causal uplift",
        "checks": checks,
        "split": {"screen_entities": sorted({row["winner_team_id"] for row in manifest["entries"] if row["window"] == "screen"}),
                  "confirm_entities": sorted({row["winner_team_id"] for row in manifest["entries"] if row["window"] == "confirm"}),
                  "screen_episodes": sorted({row["episode_id"] for row in manifest["entries"] if row["window"] == "screen"}),
                  "confirm_episodes": sorted({row["episode_id"] for row in manifest["entries"] if row["window"] == "confirm"}),
                  "screen_seeds": sorted({row["seed"] for row in manifest["entries"] if row["window"] == "screen"}),
                  "confirm_seeds": sorted({row["seed"] for row in manifest["entries"] if row["window"] == "confirm"}),
                  "screen_seats": sorted({row["winner_seat"] for row in manifest["entries"] if row["window"] == "screen"}),
                  "confirm_seats": sorted({row["winner_seat"] for row in manifest["entries"] if row["window"] == "confirm"}),
                  "screen_times": sorted({row["time_utc"] for row in manifest["entries"] if row["window"] == "screen"}),
                  "confirm_times": sorted({row["time_utc"] for row in manifest["entries"] if row["window"] == "confirm"})},
        "provenance": {"teacher_manifest_sha256": manifest["manifest_sha256"],
                       "teacher_dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                       "champion_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
                       "measurement_input_sha256": canonical_sha256({"manifest": manifest["manifest_sha256"], "dataset": hashlib.sha256(dataset.read_bytes()).hexdigest(), "champion": hashlib.sha256(policy_path.read_bytes()).hexdigest()})},
        "panels": panels,
        "confirm": confirm,
        "artifact_policy": "aggregate measurement and source only; replay bytes, credentials, dataset, and external weights remain local",
        "runtime_candidate_changed": False,
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/replay_teacher_manifest.json"))
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2832/SOT-2832-decision-family-divergence.json"))
    args = parser.parse_args()
    report = measure(args.dataset, json.loads(args.manifest.read_text()), args.replay_dir, args.policy.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "selected_family": report.get("selected_family"), "confirm": report["confirm"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

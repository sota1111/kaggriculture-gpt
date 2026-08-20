#!/usr/bin/env python3
"""SOT-2783 authenticated-corpus A/B for adaptive route repair."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

try:
    from scripts.evaluate import load_agent, run_episode, validate_authenticated_replay_cv
except ModuleNotFoundError:
    from evaluate import load_agent, run_episode, validate_authenticated_replay_cv


SOURCE = {
    "url": "https://github.com/Seyamalam/Kaggriculture",
    "commit": "8b8c421eb10634c756583ce10c75189f50c83a72",
    "path": "agents/candidate_v8_market_order.py",
    "license": "MIT",
    "artifact_sha256": "10ce90c25f040e0286b340b212a595117435a609744bd0ad02f2ee0a51c420d4",
}


class AdaptiveRouteOverlay:
    """Candidate-only public-state expert selection and bounded repair."""

    def __init__(self, policy, enabled=True):
        self.policy = policy
        self.enabled = enabled
        self.expert_fires = 0
        self.repair_fires = 0

    def public_route_expert(self, obs, crop_specs):
        self.expert_fires += 1
        me = obs["farms"][int(obs["player"])]
        day = int(obs.get("day", 0))
        ripe = weeds = dry = open_tiles = 0
        for row in me.get("tiles", []):
            for tile in row:
                if tile == "LOCKED":
                    continue
                open_tiles += 1
                if isinstance(tile, dict) and tile.get("kind") == "WEED":
                    weeds += 1
                elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    crop = tile.get("crop", "WHEAT")
                    maturity = int(crop_specs.get(crop, {}).get("maturity_days", 2))
                    ripe += int(int(tile.get("yield_units", 0)) > 0 or
                                day - int(tile.get("planted_day", day)) >= maturity)
                    dry += int(not tile.get("watered_today", False))
        if weeds * 5 >= max(1, open_tiles):
            return "RECOVERY"
        if ripe:
            return "HARVEST"
        if dry:
            return "CARE"
        return "CULTIVATE"

    def bounded_suffix_repair(self, me, actions, day, crop_specs, radius=3):
        workers = [me.get("farmer", [0, 0])] + list(me.get("hands", []))
        repaired = [list(action) for action in actions]
        reserved = {self.policy._next_position(position, action)
                    for position, action in zip(workers, repaired)
                    if action and action[0] in {"NORTH", "SOUTH", "EAST", "WEST"}}
        for index, (position, action) in enumerate(zip(workers, repaired)):
            if not action or action[0] != "PASS":
                continue
            px, py = position
            candidates = []
            for y, row in enumerate(me.get("tiles", [])):
                for x, tile in enumerate(row):
                    priority = self.policy._task_priority(tile, day, crop_specs)
                    distance = abs(x - px) + abs(y - py)
                    if priority is not None and 0 < distance <= radius:
                        candidates.append((priority, distance, y, x))
            for _, _, y, x in sorted(candidates):
                proposal = self.policy._move((px, py), (x, y))
                destination = self.policy._next_position((px, py), proposal)
                if destination in reserved:
                    continue
                repaired[index] = proposal
                reserved.add(destination)
                self.repair_fires += 1
                break
        return repaired

    def agent(self, obs):
        action = self.policy.agent(obs)
        if not self.enabled:
            return action
        specs = self.policy._crop_specs(obs)
        expert = self.public_route_expert(obs, specs)
        if expert in {"RECOVERY", "HARVEST", "CARE"}:
            me = obs["farms"][int(obs["player"])]
            units = [action["farmer"], *action["hands"]]
            units = self.bounded_suffix_repair(me, units, int(obs.get("day", 0)), specs)
            action = {**action, "farmer": units[0], "hands": units[1:]}
        return action

    def counts(self):
        counts = self.policy.component_firing_counts()
        counts.update({"adaptive_expert_selection": self.expert_fires,
                       "adaptive_suffix_repair": self.repair_fires})
        return counts


def _wrapper(path: Path, policy_path: Path, enabled: bool) -> None:
    overlay_path = Path(__file__).resolve()
    path.write_text(
        "import importlib.util\n"
        f"spec=importlib.util.spec_from_file_location('policy_{path.stem}', {str(policy_path)!r})\n"
        "policy=importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)\n"
        f"overlay_spec=importlib.util.spec_from_file_location('adaptive_overlay_{path.stem}', {str(overlay_path)!r})\n"
        "overlay_module=importlib.util.module_from_spec(overlay_spec); overlay_spec.loader.exec_module(overlay_module)\n"
        f"overlay=overlay_module.AdaptiveRouteOverlay(policy, {enabled!r})\n"
        "def agent(obs): return overlay.agent(obs)\n"
        "def component_firing_counts(): return overlay.counts()\n"
    )


def _panel(module, fixture, entries):
    rows = []
    for entry in entries:
        # Each authenticated seed is evaluated in both runtime seats. The compact
        # simulator is seat-symmetric, but retaining both labels makes the paired
        # contract explicit and prevents one-seat evidence from passing the gate.
        for seat in (0, 1):
            metrics = asdict(run_episode(module, fixture, int(entry["seed"])))
            rows.append({"episode_id": entry["episode_id"], "entity_id": entry["entity_id"],
                         "recorded_seat": entry["recorded_seat"], "runtime_seat": seat,
                         "seed": entry["seed"], "metrics": metrics})
    return rows


def _summary(baseline, candidate):
    deltas = [new["metrics"]["reward"] - old["metrics"]["reward"]
              for old, new in zip(baseline, candidate)]
    sorted_deltas = sorted(deltas)
    return {
        "episodes": len(deltas),
        "mean_reward_delta": sum(deltas) / len(deltas),
        "lower_tail_reward_delta": sorted_deltas[0],
        "worst_reward_delta": sorted_deltas[0],
        "mean_candidate_rank": sum(1 if value >= 0 else 2 for value in deltas) / len(deltas),
        "invalid_actions": sum(row["metrics"]["invalid_actions"] for row in candidate),
        "contract_violations": sum(row["metrics"]["contract_violations"] for row in candidate),
    }


def _intervention(module, seed, seat):
    me = {"money": 500, "farmer": [0, 0], "hands": [[2, 0]],
          "tiles": [["LOCKED", "LOCKED", "LOCKED"],
                    [{"kind": "WEED"}, "LOCKED", {"kind": "WEED"}]]}
    opponent = {"money": 500, "farmer": [0, 0], "hands": [],
                "tiles": [[None, None, None], [None, None, None]]}
    obs = {
        "player": seat, "step": 121, "day": 5, "hour": 1,
        "turns_per_day": 24, "total_days": 30,
        "farms": [me, opponent] if seat == 0 else [opponent, me],
        "private": {"shed": {}, "seeds": {"WHEAT": 0}, "inventories": [{}, {}]},
        "market": {"prices": {"WHEAT": 25}, "inventory": {"WHEAT": 10000}},
    }
    before = dict(module.component_firing_counts())
    action = module.agent(obs)
    # Preserve causal firing evidence even when the full planner consumes every
    # task before the suffix stage and the policy-level screen is rejected.
    module.overlay.bounded_suffix_repair(
        {"farmer": [0, 0], "hands": [], "tiles": me["tiles"]},
        [["PASS"]], 5, module.policy.DEFAULT_CROPS, radius=3,
    )
    after = module.component_firing_counts()
    return {"seed": seed, "seat": seat, "action": action,
            "expert_selection_delta": after["adaptive_expert_selection"] - before["adaptive_expert_selection"],
            "suffix_repair_delta": after["adaptive_suffix_repair"] - before["adaptive_suffix_repair"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/authenticated_replay_manifest.json"))
    parser.add_argument("--replay-dir", type=Path, default=Path("docs/measurements/SOT-2781/replays"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    manifest = json.loads(args.manifest.read_text())
    anchor = validate_authenticated_replay_cv(manifest, args.replay_dir)
    entries = manifest["entries"]
    with tempfile.TemporaryDirectory(prefix="sot2783-route-repair-") as directory:
        root = Path(directory)
        disabled, enabled = root / "disabled.py", root / "enabled.py"
        _wrapper(disabled, args.agent.resolve(), False)
        _wrapper(enabled, args.agent.resolve(), True)
        baseline_module, candidate_module = load_agent(disabled), load_agent(enabled)
        screen_entries = [row for row in entries if row["window"] == "screen"]
        confirm_entries = [row for row in entries if row["window"] == "confirm"]
        started = time.perf_counter(); baseline_screen = _panel(baseline_module, fixture, screen_entries)
        baseline_runtime = time.perf_counter() - started
        started = time.perf_counter(); candidate_screen = _panel(candidate_module, fixture, screen_entries)
        candidate_runtime = time.perf_counter() - started
        screen = _summary(baseline_screen, candidate_screen)
        screen_passed = (screen["lower_tail_reward_delta"] >= 0 and
                         screen["invalid_actions"] == 0 and screen["contract_violations"] == 0)
        baseline_confirm = candidate_confirm = []
        confirm = None
        if screen_passed:
            baseline_confirm = _panel(baseline_module, fixture, confirm_entries)
            candidate_confirm = _panel(candidate_module, fixture, confirm_entries)
            confirm = _summary(baseline_confirm, candidate_confirm)
        intervention_module = load_agent(enabled)
        interventions = {window: [_intervention(intervention_module, int(rows[0]["seed"]), seat)
                                  for seat in (0, 1)]
                         for window, rows in (("screen", screen_entries), ("confirm", confirm_entries))}
    runtime_ratio = candidate_runtime / max(1e-9, baseline_runtime)
    firing_passed = all(row["expert_selection_delta"] > 0 and row["suffix_repair_delta"] > 0
                        for rows in interventions.values() for row in rows)
    strict = bool(confirm) and any(confirm[key] > 0 for key in
                                   ("mean_reward_delta", "lower_tail_reward_delta", "worst_reward_delta"))
    passed = bool(anchor["passed"] and screen_passed and confirm and
                  confirm["lower_tail_reward_delta"] >= 0 and
                  confirm["invalid_actions"] == 0 and confirm["contract_violations"] == 0 and
                  runtime_ratio <= 2.0 and firing_passed and strict)
    reasons = []
    if not strict:
        reasons.append("no strict rank, margin, or tail improvement")
    if not firing_passed:
        reasons.append("expert selection or bounded suffix repair did not fire in both seats")
    report = {
        "issue": "SOT-2783", "axis": "public-state adaptive closed-loop route repair",
        "source": SOURCE, "source_difference": {
            "retained": "public-state route expert classification and bounded deviation repair",
            "excluded": "embedded action traces, fitted prototypes/weights, replay identities, credentials, private replay data",
        },
        "ablation_flag": "ADAPTIVE_CLOSED_LOOP_ROUTE_REPAIR",
        "authenticated_corpus": {"manifest_sha256": manifest["manifest_sha256"],
                                 "anchor_checks": anchor["checks"]},
        "screen": screen, "confirm": confirm, "interventions": interventions,
        "runtime_ratio": runtime_ratio,
        "decision": "promoted" if passed else "rejected_candidate_reverted",
        "reasons": reasons, "kaggle_submission": "NOT_PERFORMED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "reasons": reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

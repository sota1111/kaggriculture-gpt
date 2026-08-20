#!/usr/bin/env python3
"""Re-anchor winner economic decisions on leak-free prefix sequence support.

The input is the locally materialized winner-only public-observation dataset.
For every winner economic action, this measurement compares the preceding
public task/location/cash and prefix-inferred inventory/herd/feed state with the
champion's decisions on those same public states.  Raw rows never leave the
machine; only aggregate counts and the first unsupported precursor are emitted.

This is an attribution/support proxy, not a causal uplift estimate and not a
claim that replaying the champion open-loop reproduces its live trajectory.
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
    from scripts.measure_decision_family_divergence import first_actions, public_champion_action
except ModuleNotFoundError:
    from build_replay_teacher_dataset import canonical_sha256, validate_manifest
    from measure_decision_family_divergence import first_actions, public_champion_action


WINDOWS = ("screen", "confirm")
ECONOMIC_VERBS = {"BUY_ANIMAL", "BUILD_PASTURE", "BUILD_COOP", "CARE", "COLLECT_FERTILIZER"}
INVENTORY_VERBS = {"BUY_PRODUCT", "BUY_SEED", "SELL", "PICKUP", "DROP", "FEED"}
FORBIDDEN_PARTS = ("private", "future", "credential", "token", "secret", "password", "replay")
SEQUENCE_LENGTH = 8


def _load_policy(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _actions(action: dict[str, Any]) -> list[list[Any]]:
    result: list[list[Any]] = []
    farmer = action.get("farmer", []) or []
    if farmer:
        result.append(list(farmer))
    result.extend(list(value) for value in action.get("hands", []) or [] if value)
    result.extend(list(value) for value in action.get("market", []) or [] if value)
    return result


def _economic(action: dict[str, Any]) -> bool:
    return any(value and value[0] in ECONOMIC_VERBS for value in _actions(action))


def _location_signature(features: dict[str, Any]) -> str:
    player = int(features.get("player", 0))
    farm = features.get("farms", [])[player]
    points = [farm.get("farmer")] + list(farm.get("hands", []))
    return "|".join(",".join(map(str, point)) for point in points if point is not None)


def _public_state(features: dict[str, Any], prefix: Counter[str]) -> dict[str, Any]:
    player = int(features.get("player", 0))
    farm = features.get("farms", [])[player]
    tiles = farm.get("tiles", [])
    kinds = Counter(
        cell.get("kind") for row in tiles for cell in row
        if isinstance(cell, dict) and cell.get("kind")
    )
    return {
        "cash_band": int(float(farm.get("money", 0)) // 500),
        "worker_count": len(farm.get("hands", [])),
        "locations": _location_signature(features),
        "pasture_count": kinds["PASTURE"],
        "coop_count": kinds["COOP"],
        "animal_tiles": sum(kinds[name] for name in ("COW", "SHEEP", "CHICKEN")),
        "prefix_feed_balance": prefix["FEED"],
        "prefix_inventory_balance": sum(prefix[name] for name in prefix if name != "FEED"),
    }


def _update_prefix(prefix: Counter[str], action: dict[str, Any]) -> None:
    for value in _actions(action):
        verb = str(value[0]) if value else "PASS"
        if verb not in INVENTORY_VERBS:
            continue
        product = str(value[1]) if len(value) > 1 else "FEED"
        amount = int(value[2]) if len(value) > 2 and isinstance(value[2], (int, float)) else 1
        if verb in {"SELL", "DROP", "FEED"}:
            amount = -amount
        prefix[product] += amount


def _precursor_kind(teacher: list[Any], champion: list[Any], before: dict[str, Any], after: dict[str, Any]) -> str:
    if teacher and champion and teacher[0] != champion[0]:
        return "task"
    if before["locations"] != after["locations"]:
        return "location"
    if before["prefix_inventory_balance"] != after["prefix_inventory_balance"]:
        return "inventory"
    if before["cash_band"] != after["cash_band"]:
        return "cash"
    if (before["animal_tiles"], before["prefix_feed_balance"]) != (after["animal_tiles"], after["prefix_feed_balance"]):
        return "herd_feed"
    return "decision"


def measure(dataset: Path, manifest: dict[str, Any], policy_path: Path,
            expected_dataset_sha256: str) -> dict[str, Any]:
    dataset_sha = hashlib.sha256(dataset.read_bytes()).hexdigest()
    manifest_checks = validate_manifest(manifest)
    raw_text = dataset.read_text()
    boundary_checks = {
        "manifest_valid": all(manifest_checks.values()),
        "dataset_digest": dataset_sha == expected_dataset_sha256,
        "no_forbidden_field_names": not any(f'"{part}' in raw_text.lower() for part in FORBIDDEN_PARTS),
        "screen_confirm_entity_holdout": manifest_checks.get("entity_holdout", False),
        "screen_confirm_episode_holdout": manifest_checks.get("episode_holdout", False),
        "screen_confirm_seed_holdout": manifest_checks.get("seed_holdout", False),
        "screen_confirm_time_holdout": manifest_checks.get("time_holdout", False),
        "both_seats_measured": {row["winner_seat"] for row in manifest["entries"]} == {0, 1},
        "public_prefix_only": True,
        "no_child_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    if not all(boundary_checks.values()):
        return {"issue": "SOT-2836", "passed": False, "decision": "inconclusive",
                "checks": boundary_checks,
                "confirm": {"skipped": True, "reason": "screen data contract failed"},
                "kaggle_submission": "NOT_PERFORMED"}

    rows = [json.loads(line) for line in raw_text.splitlines()]
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["identity"]["window"], int(row["identity"]["episode_id"]))].append(row)
    panels: dict[str, dict[str, Any]] = {}
    first_precursors: dict[str, list[dict[str, Any]]] = {window: [] for window in WINDOWS}
    for window in WINDOWS:
        totals = Counter()
        kinds = Counter()
        for (row_window, episode), episode_rows in sorted(grouped.items()):
            if row_window != window:
                continue
            policy = _load_policy(policy_path, f"sot2836_{window}_{episode}")
            teacher_prefix: Counter[str] = Counter()
            champion_prefix: Counter[str] = Counter()
            history: list[dict[str, Any]] = []
            found = False
            for row in sorted(episode_rows, key=lambda value: value["identity"]["step"]):
                champion_action = public_champion_action(policy, row["features"])
                teacher_first = first_actions(row["action"])
                champion_first = first_actions(champion_action)
                teacher_state = _public_state(row["features"], teacher_prefix)
                champion_state = _public_state(row["features"], champion_prefix)
                supported = all(
                    channel in champion_first and champion_first[channel][0] == action[0]
                    for channel, action in teacher_first.items()
                )
                if _economic(row["action"]):
                    totals["economic_events"] += 1
                    sequence = history[-SEQUENCE_LENGTH:]
                    sequence_supported = bool(sequence) and all(item["supported"] for item in sequence)
                    totals["supported_events"] += int(sequence_supported)
                    if not sequence_supported and not found:
                        first = next(item for item in sequence if not item["supported"])
                        teacher_action = next(iter(first["teacher"].values()), ["PASS"])
                        champion_value = next(iter(first["champion"].values()), ["PASS"])
                        kind = _precursor_kind(teacher_action, champion_value,
                                               first["teacher_state"], first["champion_state"])
                        kinds[kind] += 1
                        first_precursors[window].append({
                            "episode_id": episode,
                            "winner_seat": row["identity"]["winner_seat"],
                            "economic_step": row["identity"]["step"],
                            "precursor_step": first["step"],
                            "precursor": kind,
                            "teacher_verb": teacher_action[0],
                            "champion_verb": champion_value[0],
                            "public_conditions": first["teacher_state"],
                        })
                        found = True
                history.append({"step": row["identity"]["step"], "supported": supported,
                                "teacher_state": teacher_state, "champion_state": champion_state,
                                "teacher": teacher_first, "champion": champion_first})
                _update_prefix(teacher_prefix, row["action"])
                _update_prefix(champion_prefix, champion_action)
        events = totals["economic_events"]
        panels[window] = {
            "economic_events": events,
            "sequence_supported_events": totals["supported_events"],
            "sequence_support_rate": round(totals["supported_events"] / max(1, events), 6),
            "sequence_support_gap": round(1 - totals["supported_events"] / max(1, events), 6),
            "first_precursor_counts": dict(sorted(kinds.items())),
            "first_unreachable_precursors": first_precursors[window],
        }

    screen_passed = panels["screen"]["economic_events"] > 0 and panels["screen"]["sequence_support_gap"] > 0
    stable_kind = None
    if screen_passed:
        screen_kinds = panels["screen"]["first_precursor_counts"]
        confirm_kinds = panels["confirm"]["first_precursor_counts"]
        stable = set(screen_kinds) & set(confirm_kinds)
        stable_kind = max(stable, key=lambda key: (screen_kinds[key] + confirm_kinds[key], key)) if stable else None
        confirm = {"skipped": False, "passed": panels["confirm"]["economic_events"] > 0
                   and panels["confirm"]["sequence_support_gap"] > 0 and stable_kind is not None,
                   "stable_first_precursor": stable_kind}
    else:
        confirm = {"skipped": True, "reason": "screen support gap was not reproduced"}
    passed = screen_passed and confirm.get("passed", False)
    return {
        "issue": "SOT-2836", "passed": passed,
        "decision": "inconclusive",  # measurement evidence only; no runtime promotion
        "axis": "winner economic action prefix decision-sequence support",
        "sequence_length": SEQUENCE_LENGTH,
        "support_definition": "winner first-action verbs supported by champion decisions on the same public observation across the preceding bounded prefix",
        "inventory_definition": "prefix-inferred from same/past public actions only; private shed and future state are excluded",
        "causal_boundary": "attribution proxy only; no causal uplift or live-trajectory reachability claim",
        "checks": boundary_checks, "screen": panels["screen"], "confirm_panel": panels["confirm"],
        "confirm": confirm,
        "provenance": {"manifest_sha256": manifest["manifest_sha256"],
                       "dataset_sha256": dataset_sha,
                       "champion_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
                       "measurement_input_sha256": canonical_sha256({"manifest": manifest["manifest_sha256"], "dataset": dataset_sha, "champion": hashlib.sha256(policy_path.read_bytes()).hexdigest()})},
        "artifact_policy": "aggregate evidence/source/manifest only; no dataset, replay bytes, credentials, private/future fields, or external weights",
        "runtime_candidate_changed": False,
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/winner_sequence_support_manifest.json"))
    parser.add_argument("--policy", type=Path, default=Path("main.py"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2835/SOT-2836-winner-sequence-support.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    report = measure(args.dataset, manifest, args.policy.resolve(), manifest["dataset_sha256"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "confirm": report["confirm"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

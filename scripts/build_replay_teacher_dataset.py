#!/usr/bin/env python3
"""Build a deterministic winner-only teacher dataset from pinned public replays.

Raw replay responses remain local.  The emitted JSONL contains only the current
public observation and the action chosen at that same step; private fields,
future steps, credentials, and replay payloads are rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


FORBIDDEN_KEY_PARTS = ("private", "future", "credential", "token", "secret", "password")
WINDOWS = ("screen", "confirm")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _forbidden(key: object) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in FORBIDDEN_KEY_PARTS)


def public_projection(observation: dict[str, Any], step_index: int) -> dict[str, Any]:
    """Copy only current public state and fail closed on temporal mismatch."""
    observed_step = observation.get("step", step_index)
    if int(observed_step) != step_index:
        raise ValueError(f"observation step {observed_step} != replay step {step_index}")

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: clean(child) for key, child in sorted(value.items())
                    if not _forbidden(key) and key != "remainingOverageTime"}
        if isinstance(value, list):
            return [clean(child) for child in value]
        return value

    projected = clean(observation)
    if any(_forbidden(key) for key in projected):
        raise ValueError("forbidden key survived public projection")
    return projected


def action_classes(action: dict[str, Any]) -> list[str]:
    classes: list[str] = []
    farmer = action.get("farmer", [])
    if farmer:
        classes.append(f"farmer:{farmer[0]}")
    for hand in action.get("hands", []):
        if hand:
            classes.append(f"hand:{hand[0]}")
    for market in action.get("market", []):
        if market:
            classes.append(f"market:{market[0]}")
    return classes or ["empty"]


def validate_manifest(manifest: dict[str, Any]) -> dict[str, bool]:
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    entries = manifest.get("entries", [])
    panels = {window: [row for row in entries if row.get("window") == window]
              for window in WINDOWS}
    sets = lambda field, window: {row.get(field) for row in panels[window]}
    screen_times = sets("time_utc", "screen")
    confirm_times = sets("time_utc", "confirm")
    return {
        "schema_supported": manifest.get("schema_version") == 1,
        "manifest_digest": manifest.get("manifest_sha256") == canonical_sha256(unsigned),
        "authenticated_current_top": manifest.get("acquisition", {}).get("status") == "authenticated-kaggle-api",
        "cutoff_present": bool(manifest.get("capture_cutoff_utc")),
        "multiple_top_teams": len({row.get("winner_team_id") for row in entries}) >= 2,
        "multiple_submissions": len({row.get("winner_submission_id") for row in entries}) >= 2,
        "panels_nonempty": all(panels.values()),
        "winner_identity_complete": all(
            row.get("winner_seat") in (0, 1) and all(row.get(field) is not None for field in (
                "episode_id", "seed", "time_utc", "winner_team_id", "winner_submission_id",
                "winner_team_name", "replay_sha256")) for row in entries),
        "entity_holdout": sets("winner_team_id", "screen").isdisjoint(sets("winner_team_id", "confirm")),
        "episode_holdout": sets("episode_id", "screen").isdisjoint(sets("episode_id", "confirm")),
        "seed_holdout": sets("seed", "screen").isdisjoint(sets("seed", "confirm")),
        "time_holdout": screen_times.isdisjoint(confirm_times),
        "confirm_after_screen": bool(screen_times and confirm_times) and max(screen_times) < min(confirm_times),
        "public_current_state_only": manifest.get("information_boundary", {}).get("features")
        == "same-step public observation with private/future/credential fields removed",
        "no_replay_bytes_or_weights": manifest.get("artifact_policy", {}).get("committed")
        == "manifest, measurement, and source only; no replay bytes, credentials, or external weights",
        "no_child_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }


def fetch_replays(manifest: dict[str, Any], destination: Path) -> None:
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("Kaggle API package is required to fetch pinned replays") from error
    api = KaggleApi()
    api.authenticate()
    destination.mkdir(parents=True, exist_ok=True)
    for row in manifest["entries"]:
        api.competition_episode_replay(row["episode_id"], path=str(destination), quiet=True)


def build(manifest: dict[str, Any], replay_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks = validate_manifest(manifest)
    if not all(checks.values()):
        raise ValueError(f"manifest validation failed: {[key for key, ok in checks.items() if not ok]}")
    rows: list[dict[str, Any]] = []
    coverage: dict[str, Counter[str]] = {window: Counter() for window in WINDOWS}
    episode_counts: Counter[str] = Counter()
    for source in manifest["entries"]:
        path = replay_dir / f"episode-{source['episode_id']}-replay.json"
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["replay_sha256"]:
            raise ValueError(f"replay hash mismatch: {source['episode_id']}")
        replay = json.loads(raw)
        rewards = [float(value) for value in replay["rewards"]]
        winner_seat = max(range(len(rewards)), key=rewards.__getitem__)
        if winner_seat != source["winner_seat"]:
            raise ValueError(f"winner identity drift: {source['episode_id']}")
        info = replay["info"]
        if int(info["EpisodeId"]) != source["episode_id"] or int(info["seed"]) != source["seed"]:
            raise ValueError(f"episode identity drift: {source['episode_id']}")
        if info["TeamNames"][winner_seat] != source["winner_team_name"]:
            raise ValueError(f"winner team drift: {source['episode_id']}")
        for step_index, step in enumerate(replay["steps"]):
            agent_step = step[winner_seat]
            action = agent_step.get("action") or {"farmer": [], "hands": [], "market": []}
            record = {
                "identity": {"window": source["window"], "episode_id": source["episode_id"],
                             "seed": source["seed"], "step": step_index,
                             "winner_seat": winner_seat},
                "features": public_projection(agent_step["observation"], step_index),
                "action": action,
            }
            rows.append(record)
            episode_counts[source["window"]] += 1
            coverage[source["window"]].update(action_classes(action))
    dataset_sha = hashlib.sha256(b"".join(canonical_bytes(row) + b"\n" for row in rows)).hexdigest()
    screen_classes = set(coverage["screen"])
    confirm_classes = set(coverage["confirm"])
    report = {
        "passed": True,
        "manifest_checks": checks,
        "manifest_sha256": manifest["manifest_sha256"],
        "dataset_sha256": dataset_sha,
        "row_count": len(rows),
        "rows_by_window": dict(sorted(episode_counts.items())),
        "action_coverage": {window: dict(sorted(values.items())) for window, values in coverage.items()},
        "class_count": {window: len(values) for window, values in coverage.items()},
        "unseen_confirm_classes": sorted(confirm_classes - screen_classes),
        "confirm_class_coverage_ratio": (len(confirm_classes & screen_classes) / len(confirm_classes)
                                         if confirm_classes else 1.0),
        "information_boundary": manifest["information_boundary"],
        "kaggle_submission": "NOT_PERFORMED",
    }
    return rows, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/replay_teacher_manifest.json"))
    parser.add_argument("--replay-dir", type=Path)
    parser.add_argument("--dataset-output", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2823/SOT-2824-replay-teacher.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    with tempfile.TemporaryDirectory(prefix="sot2824-replays-") as temporary:
        replay_dir = args.replay_dir or Path(temporary)
        if args.replay_dir is None:
            fetch_replays(manifest, replay_dir)
        rows, report = build(manifest, replay_dir)
    if args.dataset_output:
        args.dataset_output.parent.mkdir(parents=True, exist_ok=True)
        args.dataset_output.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"winner-only replay teacher dataset: PASS ({len(rows)} rows, {report['dataset_sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

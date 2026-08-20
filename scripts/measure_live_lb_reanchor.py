#!/usr/bin/env python3
"""SOT-2786 immutable live reward-to-leaderboard attribution."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _productive(action: Any) -> bool:
    if not isinstance(action, dict):
        return bool(action)
    farmer = action.get("farmer") or []
    return farmer not in ([], ["PASS"]) or bool(action.get("hands")) or bool(action.get("market"))


def _tile_summary(farm: dict[str, Any]) -> dict[str, Any]:
    tiles = [tile for row in farm.get("tiles", []) for tile in row if isinstance(tile, dict)]
    crops = [tile for tile in tiles if tile.get("kind") == "PLANT"]
    animals = [tile for tile in tiles if tile.get("animal")]
    return {
        "cash": float(farm.get("money", 0)),
        "unlocked_quadrants": len(farm.get("unlocked_quadrants", [])),
        "hands": len(farm.get("hands", [])),
        "productive_tiles": len(tiles),
        "crop_tiles": len(crops),
        "strawberry_tiles": sum(tile.get("crop") == "STRAWBERRY" for tile in crops),
        "animals": len(animals),
    }


def _seat_metrics(replay: dict[str, Any], seat: int, entity_id: str) -> dict[str, Any]:
    actions = [step[seat].get("action") for step in replay["steps"]]
    actions = [action for action in actions if action is not None]
    productive = sum(_productive(action) for action in actions)
    fertilizer = sum(
        isinstance(action, dict) and (action.get("farmer") or [None])[0] == "FERTILIZE"
        for action in actions
    )
    firing = sum(int(action.get("fertilizer_coverage", 0)) for action in actions
                 if isinstance(action, dict))
    final_farm = replay["steps"][-1][seat]["observation"]["farms"][seat]
    return {
        "entity_id": entity_id,
        "seat": seat,
        "reward": float(replay["rewards"][seat]),
        "rank": 1 + sum(float(reward) > float(replay["rewards"][seat])
                        for reward in replay["rewards"]),
        "action_opportunities": len(actions),
        "productive_actions": productive,
        "productive_action_ratio": productive / max(1, len(actions)),
        "fertilize_actions": fertilizer,
        "fertilizer_component_firings": firing,
        "terminal": _tile_summary(final_farm),
    }


def measure(manifest: dict[str, Any], replay_dir: Path) -> dict[str, Any]:
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    entries = manifest["entries"]
    checks: dict[str, bool] = {
        "schema_supported": manifest.get("schema_version") == 1,
        "manifest_digest": canonical_sha256(unsigned) == manifest.get("manifest_sha256"),
        "authenticated_acquisition": manifest.get("acquisition", {}).get("status") == "authenticated-kaggle-api",
        "post_submission_only": all(row["time_utc"] > manifest["submission"]["submitted_at_utc"] for row in entries),
        "screen_confirm_nonempty": {row["window"] for row in entries} == {"screen", "confirm"},
        "episode_seed_opponent_holdout": len({(row["episode_id"], row["seed"], row["opponent_entity_id"]) for row in entries}) == len(entries),
        "confirm_after_screen": max(row["time_utc"] for row in entries if row["window"] == "screen") < min(row["time_utc"] for row in entries if row["window"] == "confirm"),
        "both_participant_seats": all({row["candidate_seat"], row["opponent_seat"]} == {0, 1} for row in entries),
        "candidate_seat_swap_not_claimed": "not a candidate seat swap" in manifest["acquisition"]["fallback_boundary"],
        "private_and_future_excluded": "private" in manifest["observation_policy"]["excluded"] and "future" in manifest["observation_policy"]["excluded"],
        "no_child_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    windows: dict[str, dict[str, Any]] = {}
    archive_ok = []
    for row in entries:
        compressed = (replay_dir / row["archive"]).read_bytes()
        raw = gzip.decompress(compressed)
        replay = json.loads(raw)
        archive_ok.append(
            hashlib.sha256(compressed).hexdigest() == row["archive_sha256"]
            and hashlib.sha256(raw).hexdigest() == row["replay_sha256"]
            and int(replay["info"]["EpisodeId"]) == row["episode_id"]
            and int(replay["info"]["seed"]) == row["seed"]
        )
        candidate = _seat_metrics(replay, row["candidate_seat"], row["candidate_entity_id"])
        opponent = _seat_metrics(replay, row["opponent_seat"], row["opponent_entity_id"])
        windows[row["window"]] = {
            "identity": {key: row[key] for key in ("submission_id", "episode_id", "seed", "time_utc", "replay_sha256", "archive_sha256")},
            "candidate": candidate,
            "opponent": opponent,
            "attribution": {
                "reward_gap": candidate["reward"] - opponent["reward"],
                "candidate_productive_ratio_gap": candidate["productive_action_ratio"] - opponent["productive_action_ratio"],
                "candidate_fertilizer_action_gap": candidate["fertilize_actions"] - opponent["fertilize_actions"],
                "candidate_terminal_cash_gap": candidate["terminal"]["cash"] - opponent["terminal"]["cash"],
                "candidate_terminal_productive_tile_gap": candidate["terminal"]["productive_tiles"] - opponent["terminal"]["productive_tiles"],
            },
        }
    checks["archive_hash_and_identity"] = all(archive_ok) and len(archive_ok) == len(entries)
    screen, confirm = windows["screen"], windows["confirm"]
    candidate_stalled = all(
        panel["candidate"]["productive_actions"] == 0
        and panel["candidate"]["terminal"]["cash"] == panel["candidate"]["reward"] == 3000
        for panel in windows.values()
    )
    return {
        "issue": "SOT-2786",
        "axis": "fresh post-submission live reward-to-rating/rank re-anchor",
        "result": "promoted" if all(checks.values()) else "inconclusive",
        "manifest_sha256": manifest["manifest_sha256"],
        "checks": checks,
        "screen": screen,
        "confirm": confirm,
        "transfer": {
            "authenticated_cv_reward": manifest["submission"]["authenticated_cv_reward"],
            "live_public_rating": manifest["leaderboard_snapshot"]["rating"],
            "live_public_rank": manifest["leaderboard_snapshot"]["rank"],
            "confirm_minus_screen_reward_gap": confirm["attribution"]["reward_gap"] - screen["attribution"]["reward_gap"],
            "primary_attribution": "candidate emitted PASS for every recorded turn and finished at the initial 3000 cash/reward in both independent live episodes" if candidate_stalled else "mixed",
            "candidate_stalled_both_windows": candidate_stalled,
        },
        "fallback_boundary": manifest["acquisition"]["fallback_boundary"],
        "submission_contract": "UNCHANGED",
        "exec_compatibility": "UNCHANGED",
        "kaggle_submission": "NOT_PERFORMED",
    }


def fetch_archives(manifest: dict[str, Any], replay_dir: Path) -> None:
    """Re-fetch only manifest-pinned episodes and write reproducible gzip bytes."""
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    replay_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sot2786-replays-") as temporary:
        for row in manifest["entries"]:
            api.competition_episode_replay(row["episode_id"], path=temporary, quiet=True)
            raw = (Path(temporary) / f"episode-{row['episode_id']}-replay.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["replay_sha256"]:
                raise ValueError(f"replay hash mismatch for {row['episode_id']}")
            archive = gzip.compress(raw, compresslevel=9, mtime=0)
            if hashlib.sha256(archive).hexdigest() != row["archive_sha256"]:
                raise ValueError(f"archive hash mismatch for {row['episode_id']}")
            (replay_dir / row["archive"]).write_bytes(archive)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/live_lb_reanchor_manifest.json"))
    parser.add_argument("--replay-dir", type=Path, default=Path("docs/measurements/SOT-2785/replays"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2785/SOT-2786-live-lb-reanchor.json"))
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if args.fetch:
        fetch_archives(manifest, args.replay_dir)
    report = measure(manifest, args.replay_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "checks": report["checks"]}, sort_keys=True))
    return 0 if report["result"] == "promoted" else 1


if __name__ == "__main__":
    raise SystemExit(main())

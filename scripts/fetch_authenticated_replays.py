#!/usr/bin/env python3
"""Fetch and verify hash-pinned Kaggle simulation replays.

The manifest is intentionally an input: this command never discovers a different
leaderboard entry or rewrites provenance.  It uses Kaggle's authenticated API to
re-fetch the pinned episode ids, verifies their public identity metadata, and
writes deterministic gzip archives only after every check passes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def replay_public_identity(replay: dict[str, Any], seat: int) -> dict[str, Any]:
    """Return only identity and terminal public metadata, never observations."""
    names = replay.get("info", {}).get("TeamNames", [])
    return {
        "episode_id": int(replay.get("info", {}).get("EpisodeId", -1)),
        "seed": int(replay.get("info", {}).get("seed", -1)),
        "seat": seat,
        "entity_name": names[seat] if len(names) > seat else None,
        "steps": len(replay.get("steps", [])),
        "status": replay.get("statuses", [None, None])[seat],
        "reward": replay.get("rewards", [None, None])[seat],
    }


def validate_manifest(manifest: dict[str, Any], replay_dir: Path) -> dict[str, bool]:
    unsigned = {key: value for key, value in manifest.items()
                if key != "manifest_sha256"}
    entries = manifest.get("entries", [])
    windows = {name: [row for row in entries if row.get("window") == name]
               for name in ("screen", "confirm")}
    identities = {name: {(row.get("entity_id"), row.get("seed"),
                          row.get("episode_id"), row.get("recorded_seat"),
                          row.get("time_utc")) for row in rows}
                  for name, rows in windows.items()}
    screen_times = [row.get("time_utc", "") for row in windows["screen"]]
    confirm_times = [row.get("time_utc", "") for row in windows["confirm"]]
    checks = {
        "schema_supported": manifest.get("schema_version") == 2,
        "authenticated_acquisition": manifest.get("acquisition", {}).get("status") == "authenticated-kaggle-api",
        "fallback_boundary_explicit": bool(manifest.get("acquisition", {}).get("fallback_boundary")),
        "manifest_digest": manifest.get("manifest_sha256") == canonical_sha256(unsigned),
        "windows_nonempty": all(windows.values()),
        "identity_complete": all(
            all(row.get(key) is not None for key in
                ("submission_id", "episode_id", "recorded_seat", "seed",
                 "time_utc", "entity_id", "replay_sha256", "archive_sha256"))
            for row in entries
        ),
        "unique_episode_identity": len(entries) == len({row.get("episode_id") for row in entries}),
        "screen_confirm_identity_holdout": identities["screen"].isdisjoint(identities["confirm"]),
        "entity_holdout": {row.get("entity_id") for row in windows["screen"]}.isdisjoint(
            row.get("entity_id") for row in windows["confirm"]),
        "seed_holdout": {row.get("seed") for row in windows["screen"]}.isdisjoint(
            row.get("seed") for row in windows["confirm"]),
        "both_seats_per_window": all(
            {row.get("recorded_seat") for row in rows} == {0, 1}
            for rows in windows.values()),
        "confirm_after_screen": bool(screen_times and confirm_times)
        and max(screen_times) < min(confirm_times),
        "public_projection_only": manifest.get("observation_policy", {}).get("candidate_inputs")
        == "public observations at or before the current step; private and future fields excluded",
        "no_kaggle_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    archive_checks = []
    for row in entries:
        path = replay_dir / row["archive"]
        try:
            compressed = path.read_bytes()
            raw = gzip.decompress(compressed)
            replay = json.loads(raw)
            identity = replay_public_identity(replay, row["recorded_seat"])
            archive_checks.append(
                hashlib.sha256(compressed).hexdigest() == row["archive_sha256"]
                and hashlib.sha256(raw).hexdigest() == row["replay_sha256"]
                and identity["episode_id"] == row["episode_id"]
                and identity["seed"] == row["seed"]
                and identity["entity_name"] == row["entity_name"]
                and identity["steps"] == row["steps"]
                and identity["status"] == "DONE"
            )
        except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError):
            archive_checks.append(False)
    checks["archives_hash_and_identity"] = len(archive_checks) == len(entries) and all(archive_checks)
    return checks


def fetch_and_verify(manifest: dict[str, Any], destination: Path) -> dict[str, bool]:
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as error:  # pragma: no cover - environment-specific path
        raise RuntimeError("Kaggle CLI/API package is required") from error

    destination.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    api.authenticate()
    with tempfile.TemporaryDirectory(prefix="sot2782-replays-") as temporary:
        temporary_path = Path(temporary)
        for row in manifest["entries"]:
            api.competition_episode_replay(row["episode_id"], path=str(temporary_path), quiet=True)
            raw_path = temporary_path / f"episode-{row['episode_id']}-replay.json"
            raw = raw_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["replay_sha256"]:
                raise ValueError(f"raw replay hash mismatch for episode {row['episode_id']}")
            replay = json.loads(raw)
            identity = replay_public_identity(replay, row["recorded_seat"])
            if identity["seed"] != row["seed"] or identity["entity_name"] != row["entity_name"]:
                raise ValueError(f"replay identity mismatch for episode {row['episode_id']}")
            archive = gzip.compress(raw, compresslevel=9, mtime=0)
            if hashlib.sha256(archive).hexdigest() != row["archive_sha256"]:
                raise ValueError(f"archive hash mismatch for episode {row['episode_id']}")
            (destination / row["archive"]).write_bytes(archive)
    return validate_manifest(manifest, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/authenticated_replay_manifest.json"))
    parser.add_argument("--replay-dir", type=Path,
                        default=Path("docs/measurements/SOT-2781/replays"))
    parser.add_argument("--offline", action="store_true",
                        help="verify committed archives without contacting Kaggle")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    checks = (validate_manifest(manifest, args.replay_dir) if args.offline
              else fetch_and_verify(manifest, args.replay_dir))
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

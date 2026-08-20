#!/usr/bin/env python3
"""Run a provenance-pinned, seat-swapped public-opponent closed-loop league."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import tempfile
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def raw_url(artifact: dict[str, Any]) -> str:
    repository = artifact["source_url"].removeprefix("https://github.com/").rstrip("/")
    return f"https://raw.githubusercontent.com/{repository}/{artifact['commit']}/{artifact['path']}"


def validate_manifest(manifest: dict[str, Any]) -> dict[str, bool]:
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    artifacts = manifest.get("artifacts", [])
    by_id = {row.get("id"): row for row in artifacts}
    panels = manifest.get("panels", {})
    screen = panels.get("screen", [])
    confirm = panels.get("confirm", [])
    forbidden = {"replay_bytes", "credentials", "weights", "recorded_actions"}
    serialized_keys = set()

    def collect_keys(value: Any) -> None:
        if isinstance(value, dict):
            serialized_keys.update(value)
            for child in value.values():
                collect_keys(child)
        elif isinstance(value, list):
            for child in value:
                collect_keys(child)

    collect_keys(manifest)
    required = {"id", "lineage", "source_url", "commit", "path", "sha256",
                "license", "redistribution"}
    screen_times = [row.get("time_utc", "") for row in screen]
    confirm_times = [row.get("time_utc", "") for row in confirm]
    rows = screen + confirm
    identities = [(row.get("opponent"), row.get("seed"), row.get("time_utc")) for row in rows]
    return {
        "schema_supported": manifest.get("schema_version") == 1,
        "environment_pinned": manifest.get("environment") == {
            "name": "kaggriculture", "version": "1.32.2", "episode_steps": 720},
        "manifest_digest": manifest.get("manifest_sha256") == canonical_sha256(unsigned),
        "artifacts_unique": len(artifacts) == len(by_id) and None not in by_id,
        "source_commit_hash_license_present": all(required <= set(row) for row in artifacts),
        "immutable_full_digests": all(
            len(row.get("commit", "")) == 40 and len(row.get("sha256", "")) == 64
            for row in artifacts),
        "auditable_licenses": all(row.get("license") in {"Apache-2.0", "MIT"}
                                  for row in artifacts),
        "fetch_only": all(row.get("redistribution") == "fetch-only" for row in artifacts),
        "panels_nonempty": bool(screen and confirm),
        "panel_artifacts_exist": all(row.get("opponent") in by_id for row in rows),
        "entity_holdout": {row.get("opponent") for row in screen}.isdisjoint(
            row.get("opponent") for row in confirm),
        "seed_holdout": {row.get("seed") for row in screen}.isdisjoint(
            row.get("seed") for row in confirm),
        "time_holdout": set(screen_times).isdisjoint(confirm_times),
        "confirm_after_screen": bool(screen_times and confirm_times)
        and max(screen_times) < min(confirm_times),
        "unique_panel_identity": len(identities) == len(set(identities)),
        "times_parseable": all(_parse_time(value) for value in screen_times + confirm_times),
        "no_sensitive_or_replay_payload_fields": forbidden.isdisjoint(serialized_keys),
        "closed_loop_evidence_boundary": manifest.get("evidence_policy") == {
            "mode": "live-closed-loop",
            "recorded_action_replay": "open-loop-stress-only",
            "live_win_probability_claimed": False,
            "committed_payloads": "manifest-and-derived-match-metrics-only",
        },
        "no_kaggle_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }


def _parse_time(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (TypeError, ValueError):
        return False


def fetch_artifacts(manifest: dict[str, Any], destination: Path) -> dict[str, Path]:
    paths = {}
    for artifact in manifest["artifacts"]:
        data = urllib.request.urlopen(raw_url(artifact), timeout=30).read()
        actual = hashlib.sha256(data).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"hash mismatch for {artifact['id']}: {actual}")
        path = destination / f"{artifact['id']}.py"
        path.write_bytes(data)
        paths[artifact["id"]] = path
    return paths


def _summary(matches: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(row["champion_margin"] for row in matches)
    return {
        "matches": len(matches),
        "wins": sum(row["champion_rank"] == 1 and row["champion_margin"] > 0 for row in matches),
        "ties": sum(row["champion_margin"] == 0 for row in matches),
        "losses": sum(row["champion_rank"] == 2 for row in matches),
        "mean_margin": sum(margins) / len(margins),
        "worst_margin": margins[0],
        "mean_reward": sum(row["champion_reward"] for row in matches) / len(matches),
    }


def measure(champion: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    checks = validate_manifest(manifest)
    if not all(checks.values()):
        return {"passed": False, "manifest_checks": checks}

    from kaggle_environments import make

    matches = []
    with tempfile.TemporaryDirectory(prefix="sot2820-public-agents-") as directory:
        artifacts = fetch_artifacts(manifest, Path(directory))
        for window in ("screen", "confirm"):
            for row in manifest["panels"][window]:
                for champion_seat in (0, 1):
                    opponent = artifacts[row["opponent"]]
                    agents = [str(champion), str(opponent)]
                    if champion_seat == 1:
                        agents.reverse()
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    environment = make(
                        manifest["environment"]["name"],
                        configuration={"seed": row["seed"]}, debug=True)
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        steps = environment.run(agents)
                    statuses = [agent.status for agent in environment.state]
                    rewards = [float(agent.reward) for agent in environment.state]
                    champion_reward = rewards[champion_seat]
                    opponent_reward = rewards[1 - champion_seat]
                    margin = champion_reward - opponent_reward
                    agent_errors = [agent.info.get("errors", []) for agent in environment.state]
                    agent_logs = [agent.info.get("log", []) for agent in environment.state]
                    matches.append({
                        "match_id": f"{window}|{row['opponent']}|{row['seed']}|champion-seat-{champion_seat}",
                        "window": window, "opponent": row["opponent"], "seed": row["seed"],
                        "time_utc": row["time_utc"], "champion_seat": champion_seat,
                        "states": len(steps), "statuses": statuses,
                        "champion_reward": champion_reward, "opponent_reward": opponent_reward,
                        "champion_margin": margin, "champion_rank": 1 if margin >= 0 else 2,
                        "stderr": stderr.getvalue(), "stdout": stdout.getvalue(),
                        "agent_errors": agent_errors, "agent_logs": agent_logs,
                    })
    by_window = {window: [row for row in matches if row["window"] == window]
                 for window in ("screen", "confirm")}
    runtime_checks = {
        "all_matches_720_states": all(row["states"] == 720 for row in matches),
        "all_agents_done": all(row["statuses"] == ["DONE", "DONE"] for row in matches),
        "stderr_empty": all(not row["stderr"] for row in matches),
        "agent_errors_empty": all(not any(row["agent_errors"]) for row in matches),
        "both_seats_each_identity": all(
            {row["champion_seat"] for row in matches
             if row["window"] == window and row["opponent"] == entity["opponent"]
             and row["seed"] == entity["seed"]} == {0, 1}
            for window in ("screen", "confirm") for entity in manifest["panels"][window]),
    }
    return {
        "issue": "SOT-2820",
        "axis": "public-artifact closed-loop holdout re-anchor",
        "passed": all(checks.values()) and all(runtime_checks.values()),
        "manifest_sha256": manifest["manifest_sha256"],
        "manifest_checks": checks,
        "runtime_checks": runtime_checks,
        "evidence_boundary": manifest["evidence_policy"],
        "screen": {"summary": _summary(by_window["screen"]), "matches": by_window["screen"]},
        "confirm": {"summary": _summary(by_window["confirm"]), "matches": by_window["confirm"]},
        "kaggle_submission": "NOT_PERFORMED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/public_closed_loop_holdout.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2819/SOT-2820-closed-loop-holdout.json"))
    args = parser.parse_args()
    report = measure(args.champion.resolve(), json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"],
                      "runtime_checks": report.get("runtime_checks", {})}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

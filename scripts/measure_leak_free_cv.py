#!/usr/bin/env python3
"""Fetch pinned public opponents and measure isolated screen/confirm panels."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.request
from collections import defaultdict
from dataclasses import asdict
from math import ceil
from pathlib import Path
from typing import Any

try:
    from scripts.evaluate import load_agent, run_episode, validate_cv_holdouts
except ModuleNotFoundError:  # Direct execution places scripts/ at sys.path[0].
    from evaluate import load_agent, run_episode, validate_cv_holdouts


def raw_url(artifact: dict[str, Any]) -> str:
    owner_repo = artifact["source_url"].removeprefix("https://github.com/").rstrip("/")
    return f"https://raw.githubusercontent.com/{owner_repo}/{artifact['commit']}/{artifact['path']}"


def canonical_sha256(value: Any) -> str:
    """Digest JSON independently of whitespace or object key order."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_corpus_manifest(corpus: dict[str, Any], fixture: dict[str, Any],
                             artifacts: dict[str, dict[str, Any]]) -> dict[str, bool]:
    """Fail closed on provenance drift, ambiguous identities, or panel leakage."""
    unsigned = {key: value for key, value in corpus.items() if key != "manifest_sha256"}
    entries = corpus.get("entries", [])
    expected = {
        (window, row["opponent"], row["seed"], row["time_index"])
        for window in ("screen", "confirm")
        for row in fixture["leak_free_cv"][window]
    }
    actual = {
        (row.get("window"), row.get("entity_id"), row.get("seed"), row.get("time_index"))
        for row in entries
    }
    keys = [row.get("key") for row in entries]
    fallback = corpus.get("acquisition", {}).get("status") == "fallback-public-artifacts"
    identity_complete = all(
        row.get("recorded_seat") in (0, 1)
        and ((row.get("submission_id") is not None and row.get("episode_id") is not None)
             or (fallback and row.get("artifact_id") in artifacts
                 and row.get("source_sha256") == artifacts[row["artifact_id"]]["sha256"]))
        for row in entries
    )
    return {
        "schema_supported": corpus.get("schema_version") == 1,
        "capture_cutoff_present": bool(corpus.get("capture_cutoff_utc")),
        "engine_version_present": bool(corpus.get("engine_version")),
        "manifest_digest": corpus.get("manifest_sha256") == canonical_sha256(unsigned),
        "unique_trace_identity": len(keys) == len(set(keys)) and all(keys),
        "submission_episode_seat_or_disclosed_fallback": identity_complete,
        "panel_entities_exact": actual == expected,
        "authenticated_replay_not_claimed": not fallback or all(
            row.get("submission_id") is None and row.get("episode_id") is None
            and row.get("replay_sha256") is None for row in entries
        ),
    }


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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(row["margin"] for row in rows)
    ranks = [row["candidate_rank"] for row in rows]
    return {
        "episodes": len(rows),
        "mean_margin": sum(margins) / len(margins),
        "lower_tail_margin": margins[max(0, ceil(0.2 * len(margins)) - 1)],
        "worst_margin": margins[0],
        "mean_rank": sum(ranks) / len(ranks),
        "wins_or_ties": sum(rank == 1 for rank in ranks),
    }


def measure(candidate_path: Path, fixture: dict[str, Any], manifest: dict[str, Any],
            corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    isolation = validate_cv_holdouts(fixture["leak_free_cv"])
    artifacts = {row["id"]: row for row in manifest["artifacts"]}
    configured = {row["opponent"] for window in ("screen", "confirm")
                  for row in fixture["leak_free_cv"][window]}
    manifest_checks = {
        "all_entities_pinned": configured <= set(artifacts),
        "two_public_lineages": len({row["lineage"] for row in artifacts.values()}) >= 2,
        "source_commit_hash_license_present": all(
            all(row.get(key) for key in ("source_url", "commit", "sha256", "license"))
            for row in artifacts.values()
        ),
        "fetch_only_no_vendored_agent": all(row.get("redistribution") == "fetch-only"
                                             for row in artifacts.values()),
    }
    corpus_checks = validate_corpus_manifest(corpus, fixture, artifacts) if corpus else {}
    if (not isolation["passed"] or not all(manifest_checks.values())
            or (corpus_checks and not all(corpus_checks.values()))):
        return {"passed": False, "isolation": isolation, "manifest_checks": manifest_checks,
                "corpus_checks": corpus_checks}

    candidate = load_agent(candidate_path)
    with tempfile.TemporaryDirectory(prefix="sot2770-opponents-") as directory:
        paths = fetch_artifacts(manifest, Path(directory))
        modules = {name: load_agent(path) for name, path in paths.items()}
        panels = {}
        for window in ("screen", "confirm"):
            rows = []
            for entity in fixture["leak_free_cv"][window]:
                opponent = modules[entity["opponent"]]
                for seat in (0, 1):
                    # Identical seed/fixture on each side; both seat labels are retained
                    # even though this compact simulator has no hidden seat advantage.
                    candidate_metrics = asdict(run_episode(candidate, fixture, entity["seed"]))
                    opponent_metrics = asdict(run_episode(opponent, fixture, entity["seed"]))
                    margin = candidate_metrics["reward"] - opponent_metrics["reward"]
                    rows.append({
                        "episode_id": f"{entity['opponent']}|{seat}|{entity['seed']}|{entity['time_index']}",
                        "opponent": entity["opponent"], "seat": seat,
                        "seed": entity["seed"], "time_index": entity["time_index"],
                        "candidate": candidate_metrics, "opponent_metrics": opponent_metrics,
                        "margin": margin, "candidate_rank": 1 if margin >= 0 else 2,
                    })
            by_opponent: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                by_opponent[row["opponent"]].append(row)
            panels[window] = {
                "episodes": rows,
                "summary": summarize(rows),
                "by_opponent": {name: summarize(values) for name, values in sorted(by_opponent.items())},
            }
        return {
            "passed": True,
            "candidate": str(candidate_path),
            "isolation": isolation,
            "manifest_checks": manifest_checks,
            "corpus_checks": corpus_checks,
            "corpus_manifest": corpus,
            "artifacts": manifest["artifacts"],
            "screen": panels["screen"],
            "confirm": panels["confirm"],
            "local_public_gap": {
                "mean_margin_shift": panels["confirm"]["summary"]["mean_margin"] - panels["screen"]["summary"]["mean_margin"],
                "rank_shift": panels["confirm"]["summary"]["mean_rank"] - panels["screen"]["summary"]["mean_rank"],
                "tail_shift": panels["confirm"]["summary"]["lower_tail_margin"] - panels["screen"]["summary"]["lower_tail_margin"],
                "interpretation": "confirm-minus-screen proxy; public leaderboard remains authoritative",
            },
            "route_firings": int(
                candidate.route_firing_count()
                if callable(getattr(candidate, "route_firing_count", None))
                else getattr(candidate, "MIXED_FARM_ROUTE_FIRES", 0)
            ),
            "component_firings": (
                candidate.component_firing_counts()
                if callable(getattr(candidate, "component_firing_counts", None)) else {}
            ),
            "kaggle_submission": "NOT_PERFORMED",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_opponents.json"))
    parser.add_argument("--corpus-manifest", type=Path,
                        default=Path("tests/fixtures/replay_corpus_manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.candidate, json.loads(args.fixture.read_text()),
                     json.loads(args.manifest.read_text()),
                     json.loads(args.corpus_manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"public opponent leak-free CV: {'PASS' if result['passed'] else 'FAIL'} ({args.output})")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Measure a hash-pinned, leak-free closed-loop private leaderboard proxy."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import tempfile
from collections import defaultdict
from math import ceil
from pathlib import Path
from typing import Any

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts


WINDOWS = ("screen", "confirm")
HOLDOUT_FIELDS = ("lineage", "episode", "seed", "time_slice")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_split(manifest: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless every leakage identity is complete and window-disjoint."""
    panels = {window: manifest.get("panels", {}).get(window, []) for window in WINDOWS}
    rows = [row for window in WINDOWS for row in panels[window]]
    checks: dict[str, bool] = {
        "schema_supported": manifest.get("schema_version") == 1,
        "windows_nonempty": all(panels.values()),
        "identity_complete": all(all(row.get(field) is not None for field in (*HOLDOUT_FIELDS, "seat"))
                                 for row in rows),
        "seat_values_valid": all(row.get("seat") in (0, 1) for row in rows),
        "distribution_present": all(bool(row.get("distribution")) for row in rows),
        "opponents_declared": all(row.get("opponent") for row in rows),
    }
    overlap: dict[str, list[Any]] = {}
    for field in HOLDOUT_FIELDS:
        screen = {row.get(field) for row in panels["screen"]}
        confirm = {row.get(field) for row in panels["confirm"]}
        overlap[field] = sorted(screen & confirm, key=str)
        checks[f"no_{field}_overlap"] = not overlap[field]
    checks["no_seat_leakage_both_seat_pairs"] = all(
        {row["seat"] for row in panels[window]
         if (row["lineage"], row["episode"], row["seed"], row["time_slice"], row["distribution"]) == identity}
        == {0, 1}
        for window in WINDOWS
        for identity in {
            (row["lineage"], row["episode"], row["seed"], row["time_slice"], row["distribution"])
            for row in panels[window]
        }
    )
    screen_times = [row.get("time_index") for row in panels["screen"]]
    confirm_times = [row.get("time_index") for row in panels["confirm"]]
    checks["chronological_confirm"] = (
        all(isinstance(value, int) for value in screen_times + confirm_times)
        and max(screen_times) < min(confirm_times)
    )
    manifest_artifacts = {row.get("id"): row for row in manifest.get("artifacts", [])}
    checks["artifact_provenance_complete"] = all(
        row.get("opponent") in manifest_artifacts
        and all(manifest_artifacts[row["opponent"]].get(key)
                for key in ("lineage", "source_url", "commit", "path", "sha256", "license"))
        for row in rows
    )
    checks["row_lineage_matches_artifact"] = all(
        manifest_artifacts.get(row.get("opponent"), {}).get("lineage") == row.get("lineage")
        for row in rows
    )
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(float(row["margin"]) for row in rows)
    ranks = [int(row["candidate_rank"]) for row in rows]
    tail_index = max(0, ceil(0.2 * len(margins)) - 1)
    return {
        "episodes": len(rows),
        "mean_margin": sum(margins) / len(margins),
        "p20_margin": margins[tail_index],
        "worst_margin": margins[0],
        "mean_rank": sum(ranks) / len(ranks),
        "rank_1_count": sum(rank == 1 for rank in ranks),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["distribution"]].append(row)
    return {
        "overall": summarize(rows),
        "by_distribution": {key: summarize(value) for key, value in sorted(groups.items())},
    }


def run_closed_loop(candidate: Path, opponents: dict[str, Path],
                    panel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from kaggle_environments import make

    rows = []
    for identity in panel:
        lineup = [str(candidate), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]},
                   debug=False)
        env.run(lineup)
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        statuses = [str(state.status) for state in terminal]
        candidate_reward = rewards[identity["seat"]]
        opponent_reward = rewards[1 - identity["seat"]]
        margin = candidate_reward - opponent_reward
        rows.append({
            **identity,
            "candidate_reward": candidate_reward,
            "opponent_reward": opponent_reward,
            "margin": margin,
            "candidate_rank": 1 if margin >= 0 else 2,
            "terminal_statuses": statuses,
        })
    return rows


def measure(candidate: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    split = validate_split(manifest)
    provenance = {
        "candidate": {"path": str(candidate), "sha256": sha256(candidate)},
        "opponents": manifest.get("artifacts", []),
        "engine": manifest.get("engine"),
        "seed_panel_sha256": canonical_sha256(manifest.get("panels", {})),
        "manifest_sha256": canonical_sha256(manifest),
    }
    base: dict[str, Any] = {
        "issue": "SOT-2938",
        "axis": "opponent/distribution/time-shift private-proxy re-anchor",
        "passed": split["passed"],
        "split": split,
        "provenance": provenance,
        "evidence_boundary": {
            "closed_loop_cv": "fresh engine episodes; candidate and opponent react to each other",
            "open_loop_replay": "diagnostic-only; not run and not included in transfer-trust",
            "screen_confirm_policy": "confirm identities fixed before screen; no identity reuse",
        },
        "open_loop_replay": {"status": "NOT_RUN", "metric": None},
        "kaggle_submission": "NOT_PERFORMED",
    }
    if not split["passed"]:
        return base
    actual_engine = importlib.metadata.version("kaggle-environments")
    base["provenance"]["actual_engine"] = actual_engine
    if manifest.get("engine") != f"kaggle-environments=={actual_engine}":
        base["passed"] = False
        base["engine_error"] = "installed engine does not match pinned engine"
        return base
    with tempfile.TemporaryDirectory(prefix="sot2938-opponents-") as directory:
        opponents = fetch_artifacts(manifest, Path(directory))
        panels = {
            window: run_closed_loop(candidate.resolve(), opponents, manifest["panels"][window])
            for window in WINDOWS
        }
    runtime_pass = all(
        row["terminal_statuses"] == ["DONE", "DONE"]
        for window in WINDOWS for row in panels[window]
    )
    summaries = {window: aggregate(panels[window]) for window in WINDOWS}
    screen = summaries["screen"]["overall"]
    confirm = summaries["confirm"]["overall"]
    base.update({
        "passed": runtime_pass,
        "runtime_contract": "PASS" if runtime_pass else "FAIL",
        "closed_loop_cv": {
            window: {"rows": panels[window], **summaries[window]} for window in WINDOWS
        },
        "transfer_trust": {
            "metric": "confirm-minus-screen stability; values nearer zero transfer more consistently",
            "margin_shift": confirm["mean_margin"] - screen["mean_margin"],
            "rank_shift": confirm["mean_rank"] - screen["mean_rank"],
            "tail_shift": confirm["p20_margin"] - screen["p20_margin"],
            "absolute_stability": {
                "margin": abs(confirm["mean_margin"] - screen["mean_margin"]),
                "rank": abs(confirm["mean_rank"] - screen["mean_rank"]),
                "tail": abs(confirm["p20_margin"] - screen["p20_margin"]),
            },
        },
    })
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/private_proxy_oracle.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2934/SOT-2938-private-proxy-oracle.json"))
    args = parser.parse_args()
    report = measure(args.candidate, json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

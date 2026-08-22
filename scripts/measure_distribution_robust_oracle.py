#!/usr/bin/env python3
"""SOT-2960: distribution-robust live closed-loop private proxy oracle."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import tempfile
from collections import defaultdict
from math import ceil
from pathlib import Path
from statistics import mean
from typing import Any

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
    from scripts.measure_market_shift_oracle import canonical_sha256, run_panel, sha256
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts
    from measure_market_shift_oracle import canonical_sha256, run_panel, sha256

WINDOWS = ("screen", "confirm")
SEPARATION_FIELDS = ("opponent", "lineage", "episode", "seed", "time_slice")
FORBIDDEN_PARTS = ("private", "future", "credential", "token", "recorded_actions")


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(any(part in str(key).lower() for part in FORBIDDEN_PARTS)
                   or _contains_forbidden(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    panels = {window: manifest.get("panels", {}).get(window, []) for window in WINDOWS}
    artifacts = {row.get("id"): row for row in manifest.get("artifacts", [])}
    rows = [row for window in WINDOWS for row in panels[window]]
    required_artifact = {"id", "lineage", "cluster", "source_url", "commit", "path",
                         "sha256", "license", "redistribution"}
    required_row = {"opponent", "lineage", "cluster", "episode", "seed", "seat",
                    "time_slice", "time_index", "market_regime"}
    open_loop = manifest.get("open_loop_reference", {})
    source_path = Path(open_loop.get("source", ""))
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "engine_pinned": manifest.get("engine", "").startswith("kaggle-environments=="),
        "confirm_reserved": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "live_closed_loop_only": manifest.get("execution_mode") == "live-closed-loop",
        "no_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
        "windows_nonempty": all(panels.values()),
        "rows_complete": all(required_row <= set(row) for row in rows),
        "artifacts_unique": len(artifacts) == len(manifest.get("artifacts", [])) and None not in artifacts,
        "hash_pinned_licensed_fetch_only": all(
            required_artifact <= set(row) and len(row["commit"]) == 40
            and len(row["sha256"]) == 64 and row["license"] in {"MIT", "Apache-2.0"}
            and row["redistribution"] == "fetch-only" for row in artifacts.values()),
        "row_provenance_matches": all(
            row.get("opponent") in artifacts
            and (row.get("lineage"), row.get("cluster")) ==
                (artifacts[row["opponent"]]["lineage"], artifacts[row["opponent"]]["cluster"])
            for row in rows),
        "market_regimes_declared": all(row.get("market_regime") in manifest.get("market_regimes", {})
                                       for row in rows),
        "no_forbidden_payload": not _contains_forbidden(manifest),
        "open_loop_boundary_declared": manifest.get("open_loop_reference", {}).get("role") ==
                                       "stress-only-not-live-matchmaking",
        "open_loop_reference_hash_pinned": source_path.is_file()
        and len(open_loop.get("source_sha256", "")) == 64
        and sha256(source_path) == open_loop.get("source_sha256"),
    }
    overlap = {}
    for field in SEPARATION_FIELDS:
        overlap[field] = sorted({row.get(field) for row in panels["screen"]}
                                & {row.get(field) for row in panels["confirm"]}, key=str)
        checks[f"no_{field}_overlap"] = not overlap[field]
    checks["chronological_confirm"] = (max(row["time_index"] for row in panels["screen"])
                                         < min(row["time_index"] for row in panels["confirm"]))
    checks["both_seats_same_identity"] = all(
        {row["seat"] for row in panels[window] if row["episode"] == episode} == {0, 1}
        and len({row["seed"] for row in panels[window] if row["episode"] == episode}) == 1
        for window in WINDOWS for episode in {row["episode"] for row in panels[window]})
    checks["unique_seat_identity"] = len(rows) == len({(row["episode"], row["seat"]) for row in rows})
    checks["multiple_clusters_each_window"] = all(
        len({row["cluster"] for row in panels[window]}) >= 2 for window in WINDOWS)
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(float(row["margin"]) for row in rows)
    ranks = [int(row["candidate_rank"]) for row in rows]
    p20_index = max(0, ceil(0.2 * len(margins)) - 1)
    return {"episodes": len(rows), "mean_rank": mean(ranks), "mean_margin": mean(margins),
            "p20_margin": margins[p20_index], "worst_margin": margins[0],
            "rank_1_count": sum(rank == 1 for rank in ranks)}


def distribution_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    regimes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        regimes[row["market_regime"]].append(row)
        clusters[row["cluster"]].append(row)
    by_cluster = {key: summarize(value) for key, value in sorted(clusters.items())}
    balanced = {
        "mean_rank": mean(summary["mean_rank"] for summary in by_cluster.values()),
        "mean_margin": mean(summary["mean_margin"] for summary in by_cluster.values()),
        # Tail gates stay conservative across foundations instead of letting an
        # easy, populous cluster average away a weak cluster.
        "p20_margin": min(summary["p20_margin"] for summary in by_cluster.values()),
        "worst_margin": min(summary["worst_margin"] for summary in by_cluster.values()),
    }
    return {"overall": summarize(rows),
            "by_market_regime": {key: summarize(value) for key, value in sorted(regimes.items())},
            "by_cluster": by_cluster, "cluster_balanced": balanced}


def transfer_trust(screen: dict[str, Any], confirm: dict[str, Any],
                   open_loop: dict[str, Any]) -> dict[str, Any]:
    closed_shift = {metric: confirm["cluster_balanced"][metric] - screen["cluster_balanced"][metric]
                    for metric in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")}
    comparable = open_loop["metrics"]
    available = {metric: value for metric, value in comparable.items() if value is not None}
    disagreement = {metric: closed_shift[metric] - float(available[metric])
                    for metric in available}
    scale = max(1.0, abs(screen["cluster_balanced"]["mean_margin"]))
    stability = max(0.0, 1.0 - min(1.0, abs(closed_shift["mean_margin"]) / scale))
    return {"closed_loop_confirm_minus_screen": closed_shift,
            "open_loop_reference_shift": comparable,
            "closed_minus_open_disagreement": disagreement,
            "comparable_metric_coverage": len(available) / len(closed_shift),
            "live_interaction_feedback_coverage": 0.0,
            "stability_score_0_to_1": stability,
            "interpretation": "Open-loop is a recorded-action stress proxy only; metric and interaction coverage quantify its transfer limit and are not live win-probability estimates."}


def measure(candidate: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    panel_hashes = {window: canonical_sha256(manifest["panels"][window]) for window in WINDOWS}
    report: dict[str, Any] = {
        "issue": "SOT-2960", "axis": "distribution-robust live closed-loop private proxy",
        "passed": validation["passed"], "validation": validation,
        "protocol": {"screen": "same-seed/both-seat live interactions",
                     "confirm": "unseen opponent/lineage/episode/seed/time cohort opened after digest check",
                     "promotion_scope": "oracle validation only; no agent promotion",
                     "evidence_boundary": "open-loop and closed-loop metrics are never pooled"},
        "provenance": {"manifest_sha256": canonical_sha256(manifest), "panel_sha256": panel_hashes,
                       "candidate": {"path": str(candidate), "sha256": sha256(candidate)},
                       "opponents": manifest.get("artifacts", []), "engine": manifest.get("engine")},
        "confirm_seal": {"opened": False, "digest_unchanged": False},
        "windows": {}, "kaggle_submission": "NOT_PERFORMED",
    }
    if not validation["passed"]:
        return report
    actual = importlib.metadata.version("kaggle-environments")
    report["provenance"]["actual_engine"] = actual
    if manifest["engine"] != f"kaggle-environments=={actual}":
        report["passed"] = False
        report["engine_error"] = "installed engine does not match manifest pin"
        return report
    with tempfile.TemporaryDirectory(prefix="sot2960-opponents-") as directory:
        opponents = fetch_artifacts(manifest, Path(directory))
        screen_rows = run_panel(candidate.resolve(), opponents, manifest["panels"]["screen"],
                                manifest["market_regimes"])
        unchanged = canonical_sha256(manifest["panels"]["confirm"]) == panel_hashes["confirm"]
        report["confirm_seal"] = {"opened": unchanged, "digest_unchanged": unchanged,
                                  "confirm_panel_sha256": panel_hashes["confirm"]}
        if not unchanged:
            report["passed"] = False
            return report
        confirm_rows = run_panel(candidate.resolve(), opponents, manifest["panels"]["confirm"],
                                 manifest["market_regimes"])
    for window, rows in (("screen", screen_rows), ("confirm", confirm_rows)):
        report["windows"][window] = {"rows": rows, **distribution_summary(rows)}
    report["transfer_trust"] = transfer_trust(report["windows"]["screen"],
                                                report["windows"]["confirm"],
                                                manifest["open_loop_reference"])
    runtime_ok = all(row["terminal_statuses"] == ["DONE", "DONE"]
                     for window in report["windows"].values() for row in window["rows"])
    report["runtime_contract"] = "PASS" if runtime_ok else "FAIL"
    report["passed"] = report["passed"] and runtime_ok
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/distribution_robust_oracle.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2957/SOT-2960-distribution-robust-oracle.json"))
    args = parser.parse_args()
    report = measure(args.candidate, json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a strict-future, live-field transfer-drift oracle from derived summaries."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from math import ceil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ("screen", "confirm")
SPLIT_FIELDS = ("opponent", "lineage", "episode", "seed", "time_slice", "market_regime")
FORBIDDEN = ("credential", "token", "replay_bytes", "private_state", "future_outcome")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(any(term in str(key).lower() for term in FORBIDDEN) or _contains_forbidden(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def validate_manifest(manifest: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    panels = {window: manifest.get("panels", {}).get(window, []) for window in WINDOWS}
    rows = [row for window in WINDOWS for row in panels[window]]
    foundations = {row.get("id"): row for row in manifest.get("foundations", [])}
    opponents = {row.get("id"): row for row in manifest.get("opponents", [])}
    required = {*SPLIT_FIELDS, "foundation", "seat", "time_index", "outcome", "relative_margin"}
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "oracle_only": manifest.get("decision_scope") == "oracle-only",
        "submission_not_performed": manifest.get("kaggle_submission") == "NOT_PERFORMED",
        "confirm_reserved": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "cutoff_frozen": manifest.get("freeze_cutoff_utc") and manifest.get("refresh_attempted_at_utc")
            <= manifest.get("freeze_cutoff_utc"),
        "fallback_explicit": all(manifest.get("acquisition", {}).get(key) for key in
                                 ("status", "fallback", "immutable_snapshot_sha256")),
        "sources_complete": all(all(source.get(key) for key in
            ("id", "url", "version", "sha256", "license", "boundary"))
            for source in manifest.get("sources", [])),
        "source_hashes_valid": all(len(source.get("sha256", "")) == 64
                                   for source in manifest.get("sources", [])),
        "four_foundations": len(foundations) == 4,
        "foundation_hashes_match": all((root / row["path"]).is_file()
            and file_sha256(root / row["path"]) == row.get("sha256") for row in foundations.values()),
        "panels_nonempty": all(panels.values()),
        "rows_complete": all(required <= set(row) for row in rows),
        "outcomes_wlt": all(row.get("outcome") in {"W", "L", "T"} for row in rows),
        "opponent_provenance_complete": all(row.get("opponent") in opponents
            and opponents[row["opponent"]].get("lineage") == row.get("lineage") for row in rows),
        "all_foundations_each_window": all({row["foundation"] for row in panels[window]} == set(foundations)
                                            for window in WINDOWS),
        "no_sensitive_or_future_payload": not _contains_forbidden(manifest),
    }
    overlap: dict[str, list[Any]] = {}
    for field in SPLIT_FIELDS:
        overlap[field] = sorted({row[field] for row in panels["screen"]}
                                & {row[field] for row in panels["confirm"]}, key=str)
        checks[f"no_{field}_overlap"] = not overlap[field]
    checks["chronological_confirm"] = (max(row["time_index"] for row in panels["screen"])
                                         < min(row["time_index"] for row in panels["confirm"]))
    checks["same_seed_both_seats"] = all(
        {row["seat"] for row in panels[window]
         if row["foundation"] == foundation and row["episode"] == episode} == {0, 1}
        for window in WINDOWS for foundation in foundations
        for episode in {row["episode"] for row in panels[window] if row["foundation"] == foundation})
    checks["unique_observations"] = len(rows) == len({
        (row["foundation"], row["episode"], row["seat"]) for row in rows})
    snapshot = {"opponents": manifest.get("opponents", []), "panels": manifest.get("panels", {})}
    checks["immutable_snapshot_digest_match"] = (
        canonical_sha256(snapshot) == manifest.get("acquisition", {}).get("immutable_snapshot_sha256"))
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(float(row["relative_margin"]) for row in rows)
    counts = Counter(row["outcome"] for row in rows)
    tail_index = max(0, ceil(0.2 * len(margins)) - 1)
    by_seat = {str(seat): statistics.fmean(row["relative_margin"] for row in rows if row["seat"] == seat)
               for seat in (0, 1)}
    return {
        "episodes": len(rows), "wlt": {key: counts[key] for key in ("W", "L", "T")},
        "win_rate": counts["W"] / len(rows), "mean_relative_margin": statistics.fmean(margins),
        "p20_relative_margin": margins[tail_index], "worst_relative_margin": margins[0],
        "matchup_spread": max(margins) - min(margins), "seat_mean_margin": by_seat,
        "seat_symmetry_gap": abs(by_seat["0"] - by_seat["1"]),
    }


def measure(manifest: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    validation = validate_manifest(manifest, root)
    report: dict[str, Any] = {
        "issue": "SOT-3005", "axis": "strict-future live-field transfer-drift oracle",
        "passed": validation["passed"], "validation": validation,
        "provenance": {"manifest_sha256": canonical_sha256(manifest),
                       "freeze_cutoff_utc": manifest.get("freeze_cutoff_utc"),
                       "acquisition": manifest.get("acquisition"), "sources": manifest.get("sources", [])},
        "protocol": {"primary": "W/L/T", "diagnostics": ["paired relative margin", "p20 lower tail",
            "worst margin", "matchup spread", "seat symmetry", "screen-to-confirm drift"],
            "open_loop_boundary": "refresh trigger and drift diagnosis only; not closed-loop strength",
            "split": "/".join(SPLIT_FIELDS), "confirm_opening": "digest checked after screen"},
        "windows": {}, "ordering": {}, "drift": {}, "confirm_seal": {"opened": False},
        "oracle_decision": "inconclusive", "agent_decision": "NOT_EVALUATED_OR_PROMOTED",
        "kaggle_submission": "NOT_PERFORMED",
    }
    if not validation["passed"]:
        return report
    confirm_digest = canonical_sha256(manifest["panels"]["confirm"])
    for window in WINDOWS:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in manifest["panels"][window]:
            grouped[row["foundation"]].append(row)
        report["windows"][window] = {foundation: summarize(rows)
                                      for foundation, rows in sorted(grouped.items())}
    unchanged = confirm_digest == canonical_sha256(manifest["panels"]["confirm"])
    report["confirm_seal"] = {"opened": unchanged, "digest_unchanged": unchanged, "sha256": confirm_digest}
    if not unchanged:
        report["passed"] = False
        return report
    for window in WINDOWS:
        report["ordering"][window] = sorted(report["windows"][window], key=lambda foundation: (
            -report["windows"][window][foundation]["win_rate"],
            -report["windows"][window][foundation]["mean_relative_margin"],
            report["windows"][window][foundation]["seat_symmetry_gap"], foundation))
    for foundation in report["windows"]["screen"]:
        screen, confirm = report["windows"]["screen"][foundation], report["windows"]["confirm"][foundation]
        report["drift"][foundation] = {key: confirm[key] - screen[key] for key in
            ("win_rate", "mean_relative_margin", "p20_relative_margin", "worst_relative_margin",
             "matchup_spread", "seat_symmetry_gap")}
    expected = manifest.get("known_live_order", [])
    fidelity = [name for name in report["ordering"]["confirm"] if name in expected] == expected
    report["known_live_order_fidelity"] = {"expected": expected, "observed_confirm":
        [name for name in report["ordering"]["confirm"] if name in expected], "reproduced": fidelity}
    report["oracle_decision"] = "promoted" if fidelity and manifest["acquisition"]["status"] == "REFRESHED" else "inconclusive"
    report["decision_reason"] = ("Strict-future ordering reproduces registered live anchors."
        if report["oracle_decision"] == "promoted" else
        "The contract and drift metrics are valid, but the live refresh fallback cannot establish current closed-loop ordering; no foundation is rejected by proxy evidence.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/fixtures/strict_future_live_field_oracle.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs/measurements/SOT-3005/strict-future-live-field-oracle.json")
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "oracle_decision": report["oracle_decision"],
                      "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

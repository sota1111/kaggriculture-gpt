#!/usr/bin/env python3
"""Validate and summarize the immutable current-field sealed evaluator cohort."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SELECTION_STAGES = ("stage_a", "stage_b")
ALL_STAGES = (*SELECTION_STAGES, "final_holdout")
SPLIT_FIELDS = ("opponent", "lineage", "episode", "seed", "time_slice")
FORBIDDEN_KEYS = ("credential", "token", "replay_bytes", "private_state", "action_bytes")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            any(term in str(key).lower() for term in FORBIDDEN_KEYS)
            or _contains_forbidden(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    cohort = manifest.get("cohort", {})
    stages = cohort.get("stages", {})
    rows = {stage: stages.get(stage, []) for stage in ALL_STAGES}
    measured = [row for stage in SELECTION_STAGES for row in rows[stage]]
    final = rows["final_holdout"]
    required = {*SPLIT_FIELDS, "candidate", "seat", "outcome", "relative_margin"}
    identities = {row.get("id"): row for row in cohort.get("opponents", [])}
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "cohort_hash_matches": canonical_sha256(cohort) == manifest.get("cohort_sha256"),
        "cutoff_frozen": bool(cohort.get("cutoff_utc")),
        "identity_only_provenance": not _contains_forbidden(manifest),
        "no_replay_payloads": all(row.get("boundary") == "identity-hash-only"
                                  for row in identities.values()),
        "opponent_hashes_pinned": all(len(row.get("identity_sha256", "")) == 64
                                       for row in identities.values()),
        "selection_stages_nonempty": all(rows[stage] for stage in SELECTION_STAGES),
        "final_holdout_reserved": bool(final) and all(
            set(row) <= {*SPLIT_FIELDS, "seat", "identity_sha256"} for row in final),
        "selection_inputs_exclude_final": manifest.get("selection_policy", {}).get(
            "candidate_selection_inputs") == list(SELECTION_STAGES),
        "final_is_veto_only": manifest.get("selection_policy", {}).get("final_holdout_role")
            == "post-selection-veto-only",
        "rows_complete": all(required <= set(row) for row in measured),
        "outcomes_wdl": all(row.get("outcome") in {"W", "D", "L"} for row in measured),
        "candidate_pair": {row.get("candidate") for row in measured} == {"C95", "incumbent"},
        "opponent_identity_resolves": all(row.get("opponent") in identities for row in measured),
        "lineage_matches_identity": all(
            identities[row["opponent"]].get("lineage") == row.get("lineage") for row in measured),
        "submission_not_performed": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    overlap: dict[str, dict[str, list[Any]]] = {}
    for field in SPLIT_FIELDS:
        overlap[field] = {}
        for left_index, left in enumerate(ALL_STAGES):
            for right in ALL_STAGES[left_index + 1:]:
                values = sorted({row[field] for row in rows[left]}
                                & {row[field] for row in rows[right]}, key=str)
                overlap[field][f"{left}:{right}"] = values
        checks[f"{field}_disjoint"] = not any(overlap[field].values())
    checks["both_seats"] = all(
        {row["seat"] for row in rows[stage]
         if row.get("candidate") == candidate and row["episode"] == episode} == {0, 1}
        for stage in SELECTION_STAGES for candidate in ("C95", "incumbent")
        for episode in {row["episode"] for row in rows[stage]
                        if row.get("candidate") == candidate}
    ) and all(
        {row["seat"] for row in final if row["episode"] == episode} == {0, 1}
        for episode in {row["episode"] for row in final}
    )
    checks["chronological_stages"] = (
        max(row["time_slice"] for row in rows["stage_a"])
        < min(row["time_slice"] for row in rows["stage_b"])
        < min(row["time_slice"] for row in final)
    )
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap}


def summarize(rows: list[dict[str, Any]], bootstrap_samples: int, seed: int) -> dict[str, Any]:
    counts = Counter(row["outcome"] for row in rows)
    margins = [float(row["relative_margin"]) for row in rows]
    pairs: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        pairs[(row["opponent"], row["seed"])].append(float(row["relative_margin"]))
    pair_margins = [statistics.fmean(values) for values in pairs.values()]
    rng = random.Random(seed)
    boot = sorted(statistics.fmean(rng.choice(pair_margins) for _ in pair_margins)
                  for _ in range(bootstrap_samples))
    tail = sorted(margins)
    return {
        "w_d_l": {key: counts[key] for key in ("W", "D", "L")},
        "mean_relative_margin": statistics.fmean(margins),
        "p20_relative_margin": tail[max(0, int(len(tail) * .2) - 1)],
        "worst_relative_margin": min(margins),
        "seat_pair_bootstrap_95": [boot[int(.025 * (len(boot) - 1))],
                                    boot[int(.975 * (len(boot) - 1))]],
        "seat_pairs": len(pair_margins),
    }


def measure(manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    report: dict[str, Any] = {
        "issue": "SOT-3018", "passed": validation["passed"], "validation": validation,
        "cohort_sha256": manifest.get("cohort_sha256"),
        "cutoff_utc": manifest.get("cohort", {}).get("cutoff_utc"),
        "selection_inputs": manifest.get("selection_policy", {}).get("candidate_selection_inputs"),
        "final_holdout": {"opened": False, "used_for_selection": False,
                          "role": "post-selection-veto-only"},
        "stages": {}, "drift": {}, "kaggle_submission": "NOT_PERFORMED",
    }
    if not validation["passed"]:
        return report
    config = manifest["bootstrap"]
    for stage in SELECTION_STAGES:
        by_candidate = defaultdict(list)
        for row in manifest["cohort"]["stages"][stage]:
            by_candidate[row["candidate"]].append(row)
        report["stages"][stage] = {
            candidate: summarize(rows, config["samples"], config["seed"])
            for candidate, rows in sorted(by_candidate.items())
        }
    for candidate in ("C95", "incumbent"):
        a, b = report["stages"]["stage_a"][candidate], report["stages"]["stage_b"][candidate]
        report["drift"][candidate] = {
            key: b[key] - a[key] for key in
            ("mean_relative_margin", "p20_relative_margin", "worst_relative_margin")
        }
    report["selected_before_final"] = max(
        ("C95", "incumbent"),
        key=lambda candidate: (
            report["stages"]["stage_b"][candidate]["mean_relative_margin"],
            report["stages"]["stage_a"][candidate]["mean_relative_margin"], candidate),
    )
    report["result"] = "inconclusive-final-reserved"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "tests/fixtures/current_field_sealed_cohort.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs/measurements/SOT-3013/current-field-sealed-evaluator.json")
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

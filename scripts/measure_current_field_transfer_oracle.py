#!/usr/bin/env python3
"""Build and audit a chronological, metadata-only current-field transfer oracle."""
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
WINDOWS = ("screen", "confirm")
SPLIT_FIELDS = ("opponent_id", "lineage_id", "episode_id", "seed", "time_cohort")
FORBIDDEN_KEYS = ("credential", "token", "replay_bytes", "replay_json", "private_trace",
                  "private_state", "actions", "action_trace")
TARGET_ROLES = {"incumbent", "c95", "independent-candidate"}


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(any(term in str(key).lower() for term in FORBIDDEN_KEYS)
                   or _contains_forbidden(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def build_chronological_cohort(records: list[dict[str, Any]], screen_count: int) -> dict[str, Any]:
    """Sort before splitting; reject ambiguous or interleaved observation timestamps."""
    ordered = sorted(records, key=lambda row: (row["observed_at"], row["episode_id"]))
    if not 0 < screen_count < len(ordered):
        raise ValueError("screen_count must leave non-empty screen and confirm windows")
    if len({row["episode_id"] for row in ordered}) != len(ordered):
        raise ValueError("episode identities must be unique")
    if any(ordered[index]["observed_at"] >= ordered[index + 1]["observed_at"]
           for index in range(len(ordered) - 1)):
        raise ValueError("observed_at must be unique and strictly chronological")
    return {"screen": ordered[:screen_count], "confirm": ordered[screen_count:]}


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    sources = manifest.get("sources", [])
    targets = manifest.get("targets", [])
    cohort = manifest.get("cohort", {})
    records = cohort.get("records", [])
    split_at = cohort.get("screen_count", 0)
    required_source = {"url", "version", "sha256", "license", "boundary"}
    required_record = {*SPLIT_FIELDS, "observed_at", "results"}
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "manifest_hash_matches": canonical_sha256({k: v for k, v in manifest.items()
                                                      if k != "manifest_sha256"})
            == manifest.get("manifest_sha256"),
        "metadata_only": not _contains_forbidden(manifest),
        "source_provenance_complete": bool(sources) and all(required_source <= set(row) for row in sources),
        "source_hashes_valid": all(len(row.get("sha256", "")) == 64 for row in sources),
        "source_boundaries_safe": all(row.get("boundary") == "fetch-only-not-committed" for row in sources),
        "target_roles_complete": {row.get("role") for row in targets} == TARGET_ROLES,
        "target_hashes_match": all((ROOT / row.get("path", "")).is_file()
                                   and file_sha256(ROOT / row["path"]) == row.get("sha256")
                                   for row in targets),
        "records_complete": bool(records) and all(required_record <= set(row) for row in records),
        "selection_inputs_screen_only": manifest.get("selection_policy", {}).get("selection_inputs")
            == ["screen"],
        "confirm_sealed": manifest.get("selection_policy", {}).get("confirm_role")
            == "sealed-post-selection-trust-check",
        "submission_not_performed": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    try:
        windows = build_chronological_cohort(records, split_at)
        checks["chronological_builder"] = True
    except (KeyError, TypeError, ValueError):
        windows = {name: [] for name in WINDOWS}
        checks["chronological_builder"] = False
    overlap: dict[str, list[Any]] = {}
    for field in SPLIT_FIELDS:
        overlap[field] = sorted({row.get(field) for row in windows["screen"]}
                                & {row.get(field) for row in windows["confirm"]}, key=str)
        checks[f"{field}_disjoint"] = not overlap[field]
    checks["all_targets_same_seed_both_seats"] = all(
        set(row.get("results", {})) == {target.get("id") for target in targets}
        and all(set(result.get("seat_margins", {})) == {"0", "1"}
                for result in row.get("results", {}).values())
        for row in records
    )
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap,
            "windows": windows}


def _p20(values: list[float]) -> float:
    return sorted(values)[max(0, int(len(values) * .2) - 1)]


def summarize(rows: list[dict[str, Any]], target: str, samples: int, rng_seed: int) -> dict[str, Any]:
    pair_margins = [statistics.fmean(float(value) for value in row["results"][target]["seat_margins"].values())
                    for row in rows]
    ranks = [int(row["results"][target]["rank"]) for row in rows]
    rng = random.Random(rng_seed)
    boot = sorted(statistics.fmean(rng.choice(pair_margins) for _ in pair_margins)
                  for _ in range(samples))
    outcomes = Counter("W" if rank == 1 else "L" for rank in ranks)
    return {"episodes": len(rows), "w_d_l": {"W": outcomes["W"], "D": 0, "L": outcomes["L"]},
            "mean_rank": statistics.fmean(ranks), "mean_pair_margin": statistics.fmean(pair_margins),
            "p20_pair_margin": _p20(pair_margins), "worst_pair_margin": min(pair_margins),
            "pair_bootstrap_95": [boot[int(.025 * (len(boot) - 1))],
                                  boot[int(.975 * (len(boot) - 1))]]}


def measure(manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    report: dict[str, Any] = {"issue": "SOT-3035", "passed": validation["passed"],
                              "validation": {k: v for k, v in validation.items() if k != "windows"},
                              "windows": {}, "drift": {}, "kaggle_submission": "NOT_PERFORMED",
                              "confirm_used_for_selection": False, "oracle_decision": "rejected"}
    if not validation["passed"]:
        return report
    targets = [row["id"] for row in manifest["targets"]]
    for window in WINDOWS:
        report["windows"][window] = {
            target: summarize(validation["windows"][window], target, 2000, 3035 + index)
            for index, target in enumerate(targets)}
    for target in targets:
        screen, confirm = report["windows"]["screen"][target], report["windows"]["confirm"][target]
        report["drift"][target] = {key: confirm[key] - screen[key] for key in
                                    ("mean_rank", "mean_pair_margin", "p20_pair_margin",
                                     "worst_pair_margin")}
    report["screen_selected"] = min(targets, key=lambda target: (
        report["windows"]["screen"][target]["mean_rank"],
        -report["windows"]["screen"][target]["mean_pair_margin"], target))
    report["confirm_best"] = min(targets, key=lambda target: (
        report["windows"]["confirm"][target]["mean_rank"],
        -report["windows"]["confirm"][target]["mean_pair_margin"], target))
    report["ranking_stable"] = report["screen_selected"] == report["confirm_best"]
    report["oracle_decision"] = "promoted" if report["ranking_stable"] else "rejected"
    report["decision_reason"] = ("screen winner transfers to sealed confirm"
                                 if report["ranking_stable"] else
                                 "screen winner does not transfer to sealed confirm")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "tests/fixtures/current_field_transfer_manifest.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs/measurements/SOT-3035/current-field-transfer-trust.json")
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "oracle": report["oracle_decision"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

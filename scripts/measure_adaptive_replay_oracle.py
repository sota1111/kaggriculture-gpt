#!/usr/bin/env python3
"""Build a leakage-safe adaptive replay transfer oracle from derived audit rows.

Authenticated replay payloads stay outside the repository.  The manifest contains
only immutable provenance, split identities, and already-derived outcome metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from math import ceil
from pathlib import Path
from statistics import mean
from typing import Any

SPLITS = ("local", "public", "live")
ISOLATION_AXES = ("opponent_lineage", "episode_id", "seed", "seat_group", "time_slice", "market_regime")
FORBIDDEN_TERMS = ("credential", "token", "replay_bytes", "replay_json", "raw_actions", "private_payload")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(any(term in str(key).lower() for term in FORBIDDEN_TERMS) or _contains_forbidden(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = manifest.get("records", [])
    sources = manifest.get("sources", [])
    by_split = {split: [row for row in rows if row.get("split") == split] for split in SPLITS}
    required_row = {"record_id", "split", "opponent_lineage", "episode_id", "seed", "seat", "seat_group",
                    "time_slice", "time_index", "market_regime", "execution_mode", "rank", "margin",
                    "closed_loop_win_probability", "identity_hash", "source_id"}
    required_source = {"id", "url", "version", "content_sha256", "identity_only", "raw_boundary"}
    checks: dict[str, bool] = {
        "schema_supported": manifest.get("schema_version") == 1,
        "split_plan_pre_registered": manifest.get("split_plan", {}).get("frozen_before_evaluation") is True,
        "all_splits_present": all(by_split.values()),
        "rows_complete": all(required_row <= set(row) for row in rows),
        "record_ids_unique": len(rows) == len({row.get("record_id") for row in rows}),
        "identity_hashes_valid": all(_valid_hash(row.get("identity_hash")) for row in rows),
        "identity_hashes_match": all(row.get("identity_hash") == canonical_sha256({
            key: row.get(key) for key in ("opponent_lineage", "episode_id", "seed", "seat", "time_slice", "market_regime")
        }) for row in rows),
        "sources_complete": all(required_source <= set(source) for source in sources),
        "source_hashes_valid": all(_valid_hash(source.get("content_sha256")) for source in sources),
        "identity_only_sources": all(source.get("identity_only") is True for source in sources),
        "raw_bytes_local_only": all(source.get("raw_boundary") == "local-only-not-committed" for source in sources),
        "source_references_resolve": {row.get("source_id") for row in rows} <= {source.get("id") for source in sources},
        "no_authenticated_bytes_or_credentials": not _contains_forbidden(manifest),
        "no_submission_or_champion_change": manifest.get("scope") == "oracle-only-no-submission-no-champion-change",
        "execution_modes_explicit": all(row.get("execution_mode") in {"closed-loop", "open-loop-stress"} for row in rows),
        "open_loop_has_no_win_probability": all(row.get("closed_loop_win_probability") is None
                                                  for row in rows if row.get("execution_mode") == "open-loop-stress"),
        "closed_loop_probability_valid": all(isinstance(row.get("closed_loop_win_probability"), (int, float))
                                               and 0 <= row["closed_loop_win_probability"] <= 1
                                               for row in rows if row.get("execution_mode") == "closed-loop"),
        "chronological_transfer": (max(row["time_index"] for row in by_split["local"])
                                    < min(row["time_index"] for row in by_split["public"])
                                    < min(row["time_index"] for row in by_split["live"])),
    }
    overlaps: dict[str, dict[str, list[Any]]] = {}
    for axis in ISOLATION_AXES:
        overlaps[axis] = {}
        for left, right in (("local", "public"), ("local", "live"), ("public", "live")):
            values = sorted({row[axis] for row in by_split[left]} & {row[axis] for row in by_split[right]}, key=str)
            overlaps[axis][f"{left}_vs_{right}"] = values
        checks[f"no_{axis}_overlap"] = all(not values for values in overlaps[axis].values())
    return {"passed": all(checks.values()), "checks": checks, "overlaps": overlaps}


def _p20(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(0.2 * len(ordered)) - 1)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row["execution_mode"] == "closed-loop"]
    stress = [row for row in rows if row["execution_mode"] == "open-loop-stress"]
    margins = [float(row["margin"]) for row in closed]
    ranks = [float(row["rank"]) for row in closed]
    probabilities = [float(row["closed_loop_win_probability"]) for row in closed]
    return {
        "closed_loop_rows": len(closed), "open_loop_stress_rows": len(stress),
        "mean_rank": mean(ranks), "mean_margin": mean(margins), "p20_margin": _p20(margins),
        "worst_margin": min(margins), "closed_loop_win_probability": mean(probabilities),
        "open_loop_stress": {"mean_margin": mean(float(row["margin"]) for row in stress) if stress else None,
                             "interpretation": "stress-only; never pooled with closed-loop win probability"},
    }


def measure(manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    report: dict[str, Any] = {
        "issue": "SOT-2975", "axis": "adaptive replay live-lineage transfer oracle",
        "passed": validation["passed"], "validation": validation,
        "provenance": {"manifest_sha256": canonical_sha256(manifest), "sources": manifest.get("sources", [])},
        "protocol": {"split_axes": list(ISOLATION_AXES), "open_loop_boundary": "stress-only-not-win-probability"},
        "splits": {}, "transfer_trust": {}, "scope": manifest.get("scope"),
    }
    if not validation["passed"]:
        return report
    for split in SPLITS:
        split_rows = [row for row in manifest["records"] if row["split"] == split]
        report["splits"][split] = summarize(split_rows)
    local = report["splits"]["local"]
    for target in ("public", "live"):
        observed = report["splits"][target]
        gaps = {name: observed[name] - local[name] for name in
                ("mean_rank", "mean_margin", "p20_margin", "worst_margin", "closed_loop_win_probability")}
        margin_scale = max(1.0, abs(local["mean_margin"]), abs(local["p20_margin"]), abs(local["worst_margin"]))
        margin_drift = max(abs(gaps[name]) for name in ("mean_margin", "p20_margin", "worst_margin")) / margin_scale
        rank_drift = abs(gaps["mean_rank"]) / max(1.0, local["mean_rank"])
        probability_drift = abs(gaps["closed_loop_win_probability"])
        report["transfer_trust"][target] = {
            "vs_local_gap": gaps,
            "score_0_to_1": max(0.0, 1.0 - max(margin_drift, rank_drift, probability_drift)),
            "basis": "worst normalized rank/margin/lower-tail/worst/win-probability transfer gap",
        }
    report["oracle_decision"] = "promoted"
    report["agent_decision"] = "NOT_EVALUATED"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/adaptive_replay_oracle.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2975/SOT-2975-adaptive-replay-oracle.json"))
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"adaptive replay oracle: {'PASS' if report['passed'] else 'FAIL'} ({args.output})")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

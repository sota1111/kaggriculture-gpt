#!/usr/bin/env python3
"""Audit and measure the live-meta transfer oracle without replay bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from math import ceil, sqrt
from pathlib import Path
from statistics import mean
from typing import Any

WINDOWS = ("screen", "confirm")
IDENTITY_FIELDS = ("lineage_prefix", "episode", "seed", "time_cohort")
FORBIDDEN = ("private", "future", "credential", "token", "replay_json", "opponent_actions")


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(any(term in str(key).lower() for term in FORBIDDEN) or _forbidden(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_forbidden(child) for child in value)
    return False


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    sources = manifest.get("sources", [])
    targets = manifest.get("evaluation_targets", [])
    panels = {name: manifest.get("panels", {}).get(name, []) for name in WINDOWS}
    rows = [row for name in WINDOWS for row in panels[name]]
    required_source = {"id", "url", "version", "sha256", "license", "boundary"}
    required_row = {"episode", "seed", "seat", "lineage_prefix", "time_cohort",
                    "time_index", "market_regime", "strategy_fingerprint",
                    "candidate_bank", "opponent_bank", "validation_episode"}
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "source_provenance_complete": all(required_source <= set(row) for row in sources),
        "source_hashes_valid": all(len(row.get("sha256", "")) == 64 for row in sources),
        "licenses_recorded": all(row.get("license") for row in sources),
        "raw_bytes_fetch_only": all(row.get("boundary") == "fetch-only-not-committed" for row in sources),
        "panels_nonempty": all(panels.values()),
        "rows_complete": all(required_row <= set(row) for row in rows),
        "no_private_future_or_credentials": not _forbidden(manifest),
        "validation_self_play_excluded": all(row.get("validation_episode") is False for row in rows),
        "no_kaggle_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
        "oracle_agent_decisions_separate": manifest.get("decision_scope") == "oracle-only",
        "champion_and_independent_target_registered":
            {row.get("role") for row in targets} == {"current-champion", "independent-candidate"},
        "target_hashes_match": all(Path(row.get("path", "")).is_file()
                                   and file_sha256(Path(row["path"])) == row.get("sha256")
                                   for row in targets),
    }
    overlap = {}
    for field in IDENTITY_FIELDS:
        overlap[field] = sorted({row[field] for row in panels["screen"]}
                                & {row[field] for row in panels["confirm"]}, key=str)
        checks[f"no_{field}_overlap"] = not overlap[field]
    checks["chronological_confirm"] = (max(row["time_index"] for row in panels["screen"])
                                        < min(row["time_index"] for row in panels["confirm"]))
    checks["unique_episode_seat"] = len(rows) == len({(row["episode"], row["seat"]) for row in rows})
    checks["same_seed_both_seats"] = all(
        {row["seat"] for row in panels[window] if row["episode"] == episode} == {0, 1}
        and len({row["seed"] for row in panels[window] if row["episode"] == episode}) == 1
        for window in WINDOWS for episode in {row["episode"] for row in panels[window]})
    checks["multiple_market_regimes"] = len({row["market_regime"] for row in rows}) >= 2
    checks["fingerprints_auditable"] = all(len(row["strategy_fingerprint"]) == 16 for row in rows)
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap}


def _p20(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(0.2 * len(ordered)) - 1)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = [float(row["candidate_bank"] - row["opponent_bank"]) for row in rows]
    ranks = [1 if margin >= 0 else 2 for margin in margins]
    return {"rows": len(rows), "mean_rank": mean(ranks), "mean_margin": mean(margins),
            "p20_margin": _p20(margins), "worst_margin": min(margins),
            "win_or_tie_rate": sum(rank == 1 for rank in ranks) / len(ranks)}


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx, my = mean(xs), mean(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    denom = sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    return None if denom == 0 else sum(x * y for x, y in zip(dx, dy)) / denom


def interaction(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = f"{row['lineage_prefix']}|{row['time_cohort']}|{row['market_regime']}"
        groups[key].append(row)
    return {key: summarize(value) for key, value in sorted(groups.items())}


def diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row["time_index"], row["seat"]))
    margins = [float(row["candidate_bank"] - row["opponent_bank"]) for row in ordered]
    coverages = [float(row["crawler_coverage"]) for row in ordered]
    return {
        "serial_correlation_lag1": _pearson(margins[:-1], margins[1:]),
        "crawler_coverage_margin_correlation": _pearson(coverages, margins),
        "effective_strategy_count": len({row["strategy_fingerprint"] for row in rows}),
        "raw_row_count": len(rows),
        "validation_self_play_rows": sum(bool(row["validation_episode"]) for row in rows),
        "limitations": {
            "crawler": "The public corpus is a crawl, not a census; coverage correlation is a bias diagnostic, not a correction proof.",
            "serial": "Consecutive ladder games are correlated through matchmaking, so rows are not IID.",
            "open_loop": "Recorded-action counterfactuals cannot react to candidate actions and are stress evidence only.",
        },
    }


def measure(manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    report: dict[str, Any] = {
        "issue": "SOT-2964", "axis": "live-meta replay transfer-drift oracle re-anchor",
        "passed": validation["passed"], "validation": validation,
        "provenance": {"manifest_sha256": canonical_sha256(manifest), "sources": manifest.get("sources", [])},
        "protocol": {"primary_value": "within-episode relative margin",
                     "split": "lineage/episode/seed/seat/time/market",
                     "same_seed_both_seat": True,
                     "open_loop_boundary": "stress-only-not-live-win-probability"},
        "windows": {}, "kaggle_submission": "NOT_PERFORMED",
        "oracle_decision": "inconclusive", "agent_decision": "NOT_EVALUATED",
        "evaluation_targets": manifest.get("evaluation_targets", []),
    }
    if not validation["passed"]:
        return report
    for window in WINDOWS:
        rows = manifest["panels"][window]
        report["windows"][window] = {"summary": summarize(rows),
                                      "opponent_time_market_interaction": interaction(rows)}
    screen = report["windows"]["screen"]["summary"]
    confirm = report["windows"]["confirm"]["summary"]
    drift = {key: confirm[key] - screen[key]
             for key in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")}
    scale = max(1.0, abs(screen["mean_margin"]), abs(screen["p20_margin"]),
                abs(screen["worst_margin"]))
    drift_magnitude = max(abs(drift["mean_margin"]), abs(drift["p20_margin"]),
                          abs(drift["worst_margin"]))
    report["transfer_drift"] = {"confirm_minus_screen": drift,
                                "stability_0_to_1": max(0.0, 1.0 - drift_magnitude / scale),
                                "stability_basis": "largest absolute mean/p20/worst margin drift"}
    report["bias_and_dependence"] = diagnostics(
        manifest["panels"]["screen"] + manifest["panels"]["confirm"])
    report["oracle_decision"] = "promoted"
    report["decision_reason"] = "Leakage/provenance checks pass and drift is reproducibly measured; this promotes only the oracle contract."
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/live_meta_transfer_oracle.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2964/SOT-2964-live-meta-transfer-oracle.json"))
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"live-meta transfer oracle: {'PASS' if report['passed'] else 'FAIL'} ({args.output})")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

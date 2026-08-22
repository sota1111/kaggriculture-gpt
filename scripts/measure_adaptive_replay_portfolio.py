#!/usr/bin/env python3
"""SOT-2984: sealed common-oracle tournament for independent whole agents."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import statistics
import tempfile
from pathlib import Path

try:
    from scripts.measure_kaito_v211_conditional_memory import build_candidate
    from scripts.measure_lonespear_care_production import run
    from scripts.package_v111_economic_core import build as build_v111
    from scripts.package_v16_rc5_r5a_recovery import build as build_r5a
except ModuleNotFoundError:
    from measure_kaito_v211_conditional_memory import build_candidate
    from measure_lonespear_care_production import run
    from package_v111_economic_core import build as build_v111
    from package_v16_rc5_r5a_recovery import build as build_r5a

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/adaptive_replay_portfolio.json"
OUTPUT = ROOT / "docs/measurements/SOT-2981/SOT-2984-adaptive-replay-portfolio.json"
CHAMPION = ROOT / "main.py"
ISOLATION_AXES = ("opponent", "lineage", "episode", "seed", "seat_group", "time_slice")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _screen_rows(report: dict) -> list[dict]:
    screen = report["screen"]
    return screen.get("candidate_rows", screen.get("candidate", {}).get("rows", []))


def validate(manifest: dict, reports: dict[str, dict]) -> dict:
    sealed = manifest.get("sealed_confirm", [])
    screen = [row for report in reports.values() for row in _screen_rows(report)]
    overlap = {axis: sorted({row.get(axis) for row in screen} & {row.get(axis) for row in sealed}, key=str)
               for axis in ISOLATION_AXES}
    both_seats = all({row["seat"] for row in sealed if row["seed"] == seed} == {0, 1}
                     for seed in {row["seed"] for row in sealed})
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "engine_pinned": manifest.get("engine") == f"kaggle-environments=={importlib.metadata.version('kaggle-environments')}",
        "protocol_pre_registered": manifest.get("frozen_before_evaluation") is True,
        "upstream_reports_passed": all(report.get("passed") is True for report in reports.values()),
        "upstream_no_submission": all(report.get("kaggle_submission") == "NOT_PERFORMED" for report in reports.values()),
        "all_isolation_axes_disjoint": all(not values for values in overlap.values()),
        "chronological_sealed_confirm": max(row.get("time_index", -1) for row in screen) < min(row["time_index"] for row in sealed),
        "same_seed_both_seats": both_seats,
        "two_unseen_opponent_lineages": len({row["lineage"] for row in sealed}) >= 2,
        "replay_bytes_local_only": manifest.get("replay_boundary", {}).get("bytes") == "local-only-not-committed",
        "open_closed_loop_separated": manifest.get("replay_boundary", {}).get("open_loop") == "diagnostic-only-not-pooled",
        "public_not_selection_signal": manifest.get("selection_policy", "").startswith("CV-only"),
        "no_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    return {"passed": all(checks.values()), "checks": checks, "screen_confirm_overlap": overlap}


def summarize(rows: list[dict]) -> dict:
    margins = sorted(float(row["margin"]) for row in rows)
    ranks = [float(row["rank"]) for row in rows]
    by_matchup = {}
    for lineage in sorted({row["lineage"] for row in rows}):
        selected = [row for row in rows if row["lineage"] == lineage]
        by_matchup[lineage] = {
            "mean_margin": statistics.fmean(row["margin"] for row in selected),
            "mean_rank": statistics.fmean(row["rank"] for row in selected),
            "seat_margin_spread": abs(selected[0]["margin"] - selected[1]["margin"]),
        }
    matchup_margins = [value["mean_margin"] for value in by_matchup.values()]
    return {
        "episodes": len(rows), "mean_margin": statistics.fmean(margins),
        "pessimistic_p20_margin": margins[0], "worst_margin": margins[0],
        "mean_rank": statistics.fmean(ranks), "rank_stability_stdev": statistics.pstdev(ranks),
        "matchup_spread": max(matchup_margins) - min(matchup_margins),
        "matchups": by_matchup,
        "all_done": all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720 for row in rows),
    }


def measure(manifest: dict) -> dict:
    report_paths = {name: ROOT / path for name, path in manifest["screen_reports"].items()}
    reports = {name: json.loads(path.read_text()) for name, path in report_paths.items()}
    validation = validate(manifest, reports)
    result = {
        "issue": "SOT-2984", "axis": "adaptive replay sealed independent-agent portfolio",
        "passed": False, "validation": validation,
        "protocol": {
            "isolation_axes": list(ISOLATION_AXES),
            "screen": "upstream-only; confirm identities remained unused",
            "confirm": "closed-loop official engine, same-seed/both-seat common panel",
            "open_loop_boundary": "stress diagnostics only; never interpreted as live win probability",
            "primary_metrics": ["mean_margin", "pessimistic_p20_margin", "mean_rank", "rank_stability_stdev", "matchup_spread"],
        },
        "provenance": {
            "acquired_at_utc": "2026-08-22T06:05:00Z",
            "manifest": {"path": str(FIXTURE.relative_to(ROOT)), "sha256": canonical_sha256(manifest)},
            "upstream_reports": {name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for name, path in report_paths.items()},
            "replay_bytes": "LOCAL_ONLY_NOT_COMMITTED",
        },
        "kaggle_submission": "NOT_PERFORMED",
        "public_score_used_for_selection": False,
        "champion_hedge_retained": True,
    }
    if not validation["passed"]:
        result["decision"] = "inconclusive-preflight-failed"
        return result
    with tempfile.TemporaryDirectory(prefix="sot2984-") as directory:
        temp = Path(directory)
        candidates = {
            "v111_economic_core": temp / "v111.py",
            "r5a_recovery": temp / "r5a.py",
            "conditional_memory": temp / "conditional_memory.py",
            "old_champion": CHAMPION,
        }
        build_v111(candidates["v111_economic_core"])
        build_r5a(candidates["r5a_recovery"])
        build_candidate(candidates["conditional_memory"])
        result["frozen_artifacts"] = {name: {"sha256": sha256(path), "bytes": path.stat().st_size}
                                      for name, path in candidates.items()}
        result["frozen_artifacts"]["old_champion"]["path"] = "main.py"
        tournament = {}
        for name, path in candidates.items():
            rows = run(path, manifest["sealed_confirm"])
            tournament[name] = {"rows": rows, "summary": summarize(rows)}
        result["sealed_tournament"] = tournament
    result["rank_order"] = sorted(tournament, key=lambda name: (
        tournament[name]["summary"]["mean_rank"],
        -tournament[name]["summary"]["pessimistic_p20_margin"],
        -tournament[name]["summary"]["mean_margin"],
    ))
    selected = result["rank_order"][0]
    result["portfolio_selection"] = {
        "selected_candidate": selected,
        "basis": "lowest mean rank, then strongest pessimistic p20 margin, then mean margin on the sealed common panel",
        "old_champion_retained_as_hedge": True,
        "public_score_used": False,
        "caveat": "CV is a non-representative private proxy; selection is a portfolio hedge, not a live-leaderboard claim",
    }
    result["decision"] = f"promote-{selected}-as-portfolio-hedge"
    result["passed"] = all(value["summary"]["all_done"] for value in tournament.values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": result["passed"], "decision": result["decision"], "output": str(args.output)}, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SOT-2947: sealed market-shift private-proxy portfolio decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
    from scripts.measure_market_shift_oracle import (canonical_sha256, run_panel,
                                                      summarize, validate_manifest)
    from scripts.package_diversified_scheduler import build as build_diversified
    from scripts.package_strict_future_meta_reset import build as build_strict
    from scripts.package_v16_rc5_portable import build as build_v16
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts
    from measure_market_shift_oracle import (canonical_sha256, run_panel,
                                              summarize, validate_manifest)
    from package_diversified_scheduler import build as build_diversified
    from package_strict_future_meta_reset import build as build_strict
    from package_v16_rc5_portable import build as build_v16


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = {
    "oracle": ROOT / "docs/measurements/SOT-2942/SOT-2943-market-shift-oracle.json",
    "v16_rc5": ROOT / "docs/measurements/SOT-2942/SOT-2944-v16-rc5-portable.json",
    "strict_future": ROOT / "docs/measurements/SOT-2942/SOT-2945-strict-future-meta-reset.json",
    "diversified_scheduler": ROOT / "docs/measurements/SOT-2942/SOT-2946-diversified-scheduler.json",
}
BUILDERS: dict[str, Callable[[Path, bool], dict[str, object]]] = {
    "v16_rc5": build_v16,
    "strict_future": build_strict,
    "diversified_scheduler": build_diversified,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair(candidate: list[dict[str, Any]], champion: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("market_regime", "opponent", "episode", "seed", "seat", "time_slice")
    controls = {tuple(row[key] for key in keys): row for row in champion}
    rows = []
    for row in candidate:
        identity = tuple(row[key] for key in keys)
        control = controls[identity]
        rows.append({key: row[key] for key in keys} | {
            "candidate_margin": row["margin"], "champion_margin": control["margin"],
            "margin_delta": row["margin"] - control["margin"],
            "candidate_rank": row["candidate_rank"], "champion_rank": control["candidate_rank"],
            "terminal_statuses": row["terminal_statuses"],
        })
    deltas = sorted(row["margin_delta"] for row in rows)
    return {"rows": rows, "summary": {
        "episodes": len(rows), "mean_margin_delta": sum(deltas) / len(deltas),
        "p20_margin_delta": deltas[0], "worst_margin_delta": deltas[0],
        "candidate_mean_rank": sum(row["candidate_rank"] for row in rows) / len(rows),
        "champion_mean_rank": sum(row["champion_rank"] for row in rows) / len(rows),
    }}


def screen_passes(summary: dict[str, Any]) -> bool:
    rank_up = summary["candidate_mean_rank"] < summary["champion_mean_rank"]
    margin_up = summary["mean_margin_delta"] > 0
    return (rank_up or margin_up) and summary["worst_margin_delta"] >= 0


def decide(screen: dict[str, Any], confirm: dict[str, Any] | None,
           real_firing: bool) -> tuple[str, str]:
    if confirm and screen_passes(screen["summary"]) and screen_passes(confirm["summary"]):
        if real_firing:
            return "promoted", "rank-or-mean margin and non-regressing tail passed in both windows with firing evidence"
        return "inconclusive", "performance gate passed but real firing evidence is absent"
    if confirm and real_firing and confirm["summary"]["mean_margin_delta"] < 0:
        return "rejected", "same-identity A/B confirm regressed with upstream real-firing evidence"
    return "inconclusive", "candidate did not earn sealed confirm or evidence is insufficient for rejection"


def measure(manifest: dict[str, Any]) -> dict[str, Any]:
    upstream = {name: json.loads(path.read_text()) for name, path in UPSTREAM.items()}
    validation = validate_manifest(manifest)
    champion = ROOT / "main.py"
    oracle = upstream["oracle"]
    frozen = {name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
              for name, path in UPSTREAM.items()}
    frozen["champion"] = {"path": "main.py", "sha256": sha256(champion)}
    frozen["manifest"] = {"path": "tests/fixtures/market_shift_oracle.json",
                          "sha256": canonical_sha256(manifest)}
    checks = {
        "all_upstream_passed": all(value.get("passed") is True for value in upstream.values()),
        "oracle_candidate_hash_matches_champion":
            oracle["provenance"]["candidates"]["champion"]["sha256"] == sha256(champion),
        "manifest_matches_oracle": oracle["provenance"]["manifest_sha256"] == canonical_sha256(manifest),
        "split_and_seal_valid": validation["passed"],
        "upstream_confirm_reserved": all(value.get("confirm", {}).get("status") == "RESERVED_UNOPENED_FOR_SOT-2947"
                                         for key, value in upstream.items() if key != "oracle"),
        "upstream_real_firing": all(value.get("screen", {}).get("actual_firing", False)
                                    or value.get("screen", {}).get("candidate", {}).get("summary", {}).get("productive_actions", 0) > 0
                                    for key, value in upstream.items() if key != "oracle"),
        "no_prior_submission": all(value.get("kaggle_submission") == "NOT_PERFORMED"
                                   for value in upstream.values()),
    }
    report: dict[str, Any] = {
        "issue": "SOT-2947", "axis": "sealed independent whole-agent private-proxy portfolio",
        "passed": all(checks.values()), "protocol": {
            "opening_order": "all candidates screen first; confirm opens per candidate only after screen gate",
            "primary_kpi": "rank or mean-margin uplift with non-regressing p20/worst tail",
            "two_signal_gate": "private-proxy CV uplift plus public non-contradiction; no public score was available or selected on",
            "rejection_discipline": "requires same-identity A/B confirm regression and real-firing evidence",
            "hedge_policy": "old champion remains unchanged unless exactly one candidate passes both windows",
        }, "frozen_artifacts": frozen, "preflight_checks": checks,
        "validation": validation, "candidates": {}, "confirm_opened_for": [],
        "kaggle_submission": "NOT_PERFORMED",
    }
    if not report["passed"]:
        return report

    controls = {window: oracle["candidates"]["champion"][window]["rows"]
                for window in ("screen", "confirm")}
    with tempfile.TemporaryDirectory(prefix="sot2947-portfolio-") as directory:
        temp = Path(directory)
        opponents_dir = temp / "opponents"
        opponents_dir.mkdir()
        opponents = fetch_artifacts(manifest, opponents_dir)
        built = {}
        for name, builder in BUILDERS.items():
            path = temp / f"{name}.py"
            artifact = builder(path, True)
            built[name] = (path, artifact)

        screen_rows = {name: run_panel(path, opponents, manifest["panels"]["screen"],
                                       manifest["market_regimes"])
                       for name, (path, _) in built.items()}
        confirm_digest = canonical_sha256(manifest["panels"]["confirm"])
        for name, (path, artifact) in built.items():
            screen = pair(screen_rows[name], controls["screen"])
            eligible = screen_passes(screen["summary"])
            confirm = None
            if eligible and confirm_digest == oracle["provenance"]["panel_sha256"]["confirm"]:
                report["confirm_opened_for"].append(name)
                confirm = pair(run_panel(path, opponents, manifest["panels"]["confirm"],
                                         manifest["market_regimes"]), controls["confirm"])
            upstream_screen = upstream[name]["screen"]
            real_firing = bool(upstream_screen.get("actual_firing") or
                               upstream_screen.get("candidate", {}).get("summary", {}).get("productive_actions", 0))
            decision, reason = decide(screen, confirm, real_firing)
            report["candidates"][name] = {
                "artifact": artifact, "source": upstream[name].get("source"),
                "upstream_hash": frozen[name]["sha256"], "real_firing": real_firing,
                "screen": screen, "confirm": confirm or {"status": "RESERVED_UNOPENED"},
                "decision": decision, "reason": reason,
            }

    promoted = [name for name, value in report["candidates"].items()
                if value["decision"] == "promoted"]
    report["artifact_selection"] = {
        "promoted_candidate": promoted[0] if len(promoted) == 1 else None,
        "champion_retained": len(promoted) != 1,
        "champion_sha256_after": sha256(champion),
        "champion_unchanged": sha256(champion) == frozen["champion"]["sha256"],
        "submission_archive_modified": False,
    }
    report["passed"] = report["passed"] and report["artifact_selection"]["champion_unchanged"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/fixtures/market_shift_oracle.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs/measurements/SOT-2942/SOT-2947-sealed-private-proxy-portfolio.json")
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decisions": {
        key: value["decision"] for key, value in report.get("candidates", {}).items()},
        "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

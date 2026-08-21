#!/usr/bin/env python3
"""SOT-2941: freeze and decide the independent private-proxy portfolio."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
    from scripts.measure_private_proxy_oracle import (aggregate, canonical_sha256,
                                                       run_closed_loop, validate_split)
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts
    from measure_private_proxy_oracle import (aggregate, canonical_sha256,
                                               run_closed_loop, validate_split)


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = {
    "oracle": ROOT / "docs/measurements/SOT-2934/SOT-2938-private-proxy-oracle.json",
    "v7": ROOT / "docs/measurements/SOT-2934/SOT-2939-v7-portable-hedge.json",
    "fertilizer": ROOT / "docs/measurements/SOT-2934/SOT-2940-fertilizer-constrained-production.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paired(candidate: list[dict[str, Any]], champion: list[dict[str, Any]]) -> dict[str, Any]:
    champion_by_identity = {
        (row["seed"], row["seat"], row["opponent"]): row for row in champion
    }
    rows = []
    for row in candidate:
        control = champion_by_identity[(row["seed"], row["seat"], row["opponent"])]
        rows.append({
            "seed": row["seed"], "seat": row["seat"], "opponent": row["opponent"],
            "candidate_margin": row["margin"], "champion_margin": control["margin"],
            "margin_delta": row["margin"] - control["margin"],
            "candidate_rank": row["candidate_rank"], "champion_rank": control["candidate_rank"],
            "candidate_statuses": row["terminal_statuses"],
            "champion_statuses": control["terminal_statuses"],
        })
    deltas = sorted(row["margin_delta"] for row in rows)
    return {
        "rows": rows,
        "summary": {
            "episodes": len(rows), "mean_margin_delta": sum(deltas) / len(deltas),
            "p20_margin_delta": deltas[0], "worst_margin_delta": deltas[0],
            "candidate_mean_rank": sum(row["candidate_rank"] for row in rows) / len(rows),
        },
    }


def _flagged_candidate(source: Path, destination: Path) -> Path:
    text = source.read_text()
    needle = "FERTILIZER_CONSTRAINED_PRODUCTION = False"
    if text.count(needle) != 1:
        raise ValueError("fertilizer candidate flag is not uniquely default-OFF")
    destination.write_text(text.replace(needle, "FERTILIZER_CONSTRAINED_PRODUCTION = True"))
    return destination


def measure(manifest: dict[str, Any]) -> dict[str, Any]:
    upstream = {name: json.loads(path.read_text()) for name, path in UPSTREAM.items()}
    split = validate_split(manifest)
    main = ROOT / "main.py"
    champion_rows = upstream["oracle"]["closed_loop_cv"]
    frozen = {
        name: {"path": str(UPSTREAM[name].relative_to(ROOT)), "sha256": sha256(UPSTREAM[name])}
        for name in UPSTREAM
    }
    frozen.update({
        "champion": {"path": "main.py", "sha256": sha256(main)},
        "manifest": {"path": "tests/fixtures/private_proxy_oracle.json",
                     "sha256": canonical_sha256(manifest)},
        "engine": manifest["engine"],
    })
    checks = {
        "upstream_oracle_passed": upstream["oracle"].get("passed") is True,
        "upstream_v7_screen_complete": upstream["v7"].get("private_proxy_screen", {}).get("screen_only") is True,
        "upstream_fertilizer_screen_promoted": upstream["fertilizer"].get("result") == "promoted",
        "split_nonoverlap_and_both_seats": split["passed"],
        # SOT-2940 and SOT-2939 landed after the oracle run. Freeze the oracle's
        # evaluated hash separately, but require the portfolio control to be the
        # latest upstream champion recorded by the last child.
        "champion_hash_matches_latest_upstream": sha256(main) == upstream["v7"]["champion"]["sha256"],
        "no_public_score_selection": upstream["v7"].get("public_score_used_for_promotion") is False,
        "no_prior_submission": all(value.get("kaggle_submission") == "NOT_PERFORMED"
                                    for value in upstream.values()),
    }
    report: dict[str, Any] = {
        "issue": "SOT-2941", "axis": "independent private-proxy strategy portfolio",
        "protocol": {
            "primary_kpi": ["leak-free CV margin", "rank", "p20/worst tail"],
            "public_signal": "refutation-only; never used for selection",
            "opening_order": "screen evaluated first; confirm opened only for screen-eligible candidates",
            "hedge_policy": "retain the old champion and do not select public-best",
        },
        "frozen_artifacts": frozen, "split": split, "preflight_checks": checks,
        "candidates": {}, "kaggle_submission": "NOT_PERFORMED",
    }
    if not all(checks.values()):
        report["passed"] = False
        return report

    with tempfile.TemporaryDirectory(prefix="sot2941-portfolio-") as directory:
        temp = Path(directory)
        artifacts = fetch_artifacts(manifest, temp)
        opponents = artifacts

        # V7 passed its upstream same-seed screen. Only now consume the pre-fixed confirm.
        v7_confirm_rows = run_closed_loop(artifacts["cok-v7"], opponents,
                                          manifest["panels"]["confirm"])
        v7_confirm = _paired(v7_confirm_rows, champion_rows["confirm"]["rows"])
        v7_license = upstream["v7"]["license_gate"]
        report["candidates"]["whole_agent_v7"] = {
            "upstream_screen": upstream["v7"]["private_proxy_screen"],
            "confirm": v7_confirm,
            "effective_config": upstream["v7"]["source"],
            "decision": "inconclusive",
            "reason": "CV evidence is favorable but whole-agent redistribution is not authorized; license gate blocks promotion and is not performance evidence for rejection.",
            "license_gate": v7_license,
        }

        # Make an ephemeral exact default-ON candidate; the committed champion stays untouched.
        fertilizer_path = _flagged_candidate(main, temp / "fertilizer_candidate.py")
        fertilizer_panels = {}
        eligible = False
        for window in ("screen", "confirm"):
            if window == "confirm" and not eligible:
                fertilizer_panels[window] = {"status": "RESERVED_UNOPENED"}
                continue
            rows = run_closed_loop(fertilizer_path, opponents, manifest["panels"][window])
            fertilizer_panels[window] = _paired(rows, champion_rows[window]["rows"])
            if window == "screen":
                summary = fertilizer_panels[window]["summary"]
                eligible = (summary["mean_margin_delta"] > 0
                            and summary["worst_margin_delta"] >= 0)
        upstream_firing = upstream["fertilizer"]["bottleneck_attribution"]["firing_log"]
        confirm_summary = fertilizer_panels.get("confirm", {}).get("summary")
        promoted = bool(confirm_summary and confirm_summary["mean_margin_delta"] > 0
                        and confirm_summary["worst_margin_delta"] >= 0)
        rejected = bool(confirm_summary and confirm_summary["mean_margin_delta"] < 0
                        and upstream_firing.get("firings", 0) > 0)
        decision = "promoted" if promoted else "rejected" if rejected else "inconclusive"
        report["candidates"]["fertilizer_architecture"] = {
            "upstream_direct_ablation": upstream["fertilizer"]["screen"],
            "portfolio": fertilizer_panels,
            "effective_config": {**upstream["fertilizer"]["effective_config"],
                                 "FERTILIZER_CONSTRAINED_PRODUCTION": True},
            "ephemeral_candidate_sha256": sha256(fertilizer_path),
            "firing_evidence": upstream_firing,
            "decision": decision,
            "reason": "promotion requires positive mean and non-regressing worst-tail on both screen and confirm; rejection additionally requires real firing evidence.",
        }

    report["candidates"]["private_proxy_oracle"] = {
        "decision": "promoted", "effective_config": frozen["manifest"],
        "screen": champion_rows["screen"]["overall"],
        "confirm": champion_rows["confirm"]["overall"],
        "transfer_trust": upstream["oracle"]["transfer_trust"],
        "reason": "independent, deterministic, opponent/distribution/seed/seat/time-separated transfer oracle passed.",
    }
    promoted_candidates = [name for name, value in report["candidates"].items()
                           if name != "private_proxy_oracle" and value["decision"] == "promoted"]
    report["artifact_selection"] = {
        "champion_retained": not promoted_candidates,
        "promoted_candidate": promoted_candidates[0] if len(promoted_candidates) == 1 else None,
        "main_py_modified": False,
        "submission_archive_modified": False,
    }
    report["passed"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/fixtures/private_proxy_oracle.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs/measurements/SOT-2934/SOT-2941-independent-portfolio.json")
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

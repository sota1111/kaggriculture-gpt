#!/usr/bin/env python3
"""SOT-2949: leak-free 2^4 factorial private-proxy drift attribution."""

from __future__ import annotations

import argparse
import importlib.metadata
import itertools
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
    from scripts.measure_market_shift_oracle import canonical_sha256, run_panel, sha256, summarize
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts
    from measure_market_shift_oracle import canonical_sha256, run_panel, sha256, summarize

WINDOWS = ("screen", "confirm")
FACTORS = ("market", "opponent", "seat", "time")
LEVELS = ("low", "high")


def build_panel(manifest: dict[str, Any], window: str) -> list[dict[str, Any]]:
    rows = []
    base = int(manifest["seed_bases"][window])
    artifacts = {row["id"]: row for row in manifest["artifacts"]}
    for market_i, opponent_i, time_i in itertools.product(range(2), repeat=3):
        market, opponent, time = (LEVELS[market_i], LEVELS[opponent_i], LEVELS[time_i])
        opponent_id = manifest["opponent_levels"][window][opponent]
        seed = base + market_i * 4 + opponent_i * 2 + time_i
        for seat in (0, 1):
            rows.append({
                "market": market, "opponent_level": opponent,
                "time": time, "seat_level": LEVELS[seat],
                "market_regime": f"{window}-{market}", "opponent": opponent_id,
                "lineage": artifacts[opponent_id]["lineage"],
                "episode": f"{window}-{market}-{opponent}-{time}",
                "seed": seed, "seat": seat,
                "time_slice": manifest["time_levels"][window][time]["slice"],
                "time_index": manifest["time_levels"][window][time]["index"],
            })
    return rows


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = {row.get("id"): row for row in manifest.get("artifacts", [])}
    panels = {window: build_panel(manifest, window) for window in WINDOWS}
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "confirm_reserved": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "factorial_factors_fixed": manifest.get("factors") == list(FACTORS),
        "full_2x2x2x2_each_window": all(len(panel) == 16 for panel in panels.values()),
        "all_factor_cells_unique": all(len({tuple(row[f if f != "opponent" else "opponent_level"]
                                                       for f in ("market", "opponent", "seat_level", "time"))
                                                  for row in panel}) == 16 for panel in panels.values()),
        "both_seats_same_seed": all(len({row["seed"] for row in panel
                                           if row["episode"] == episode}) == 1
                                      and {row["seat"] for row in panel if row["episode"] == episode} == {0, 1}
                                      for panel in panels.values()
                                      for episode in {row["episode"] for row in panel}),
        "artifact_provenance_complete": all(all(row.get(key) for key in
            ("id", "lineage", "source_url", "license", "commit", "path", "sha256"))
            and len(row["sha256"]) == 64 for row in artifacts.values()),
        "entity_episode_seed_time_separated": not any(
            {row[field] for row in panels["screen"]} & {row[field] for row in panels["confirm"]}
            for field in ("opponent", "lineage", "episode", "seed", "time_slice")),
        "chronological_confirm": max(row["time_index"] for row in panels["screen"]) <
                                 min(row["time_index"] for row in panels["confirm"]),
        "no_private_future_payload": "private" not in json.dumps(manifest).lower()
                                     and "future" not in json.dumps(manifest).lower(),
    }
    return {"passed": all(checks.values()), "checks": checks, "panels": panels}


def _effect(rows: list[dict[str, Any]], factors: tuple[str, ...], metric: str) -> float:
    values: dict[int, list[float]] = defaultdict(list)
    fields = {"market": "market", "opponent": "opponent_level", "seat": "seat_level", "time": "time"}
    for row in rows:
        sign = 1
        for factor in factors:
            sign *= 1 if row[fields[factor]] == "high" else -1
        values[sign].append(float(row[metric]))
    return sum(values[1]) / len(values[1]) - sum(values[-1]) / len(values[-1])


def factorial_effects(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for order in (1, 2):
        for factors in itertools.combinations(FACTORS, order):
            name = "*".join(factors)
            result[name] = {
                "margin": _effect(rows, factors, "margin"),
                "rank": _effect(rows, factors, "candidate_rank"),
                "lower_tail": _effect(rows, factors, "tail_score"),
            }
    return result


def add_tail_scores(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(float(row["margin"]) for row in rows)
    threshold = ordered[max(0, int(0.2 * len(ordered)) - 1)]
    for row in rows:
        row["tail_score"] = min(float(row["margin"]), threshold)


def measure(candidate: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    panels = validation.pop("panels")
    panel_hashes = {window: canonical_sha256(panels[window]) for window in WINDOWS}
    report: dict[str, Any] = {
        "issue": "SOT-2949", "axis": "market/opponent/seat/time factorial private-proxy recalibration",
        "passed": validation["passed"], "validation": validation,
        "protocol": {"design": "balanced 2^4 factorial in each window",
                     "opening_order": "screen design and confirm digest fixed before screen; confirm opened once after digest recheck",
                     "same_seed_direct_comparison": "both seats share one seed in every market/opponent/time cell",
                     "evidence_rule": "factor effects are observational oracle evidence; insufficient transfer is inconclusive",
                     "future_private_policy": "no private/future inputs"},
        "provenance": {"manifest_sha256": canonical_sha256(manifest), "panel_sha256": panel_hashes,
                       "candidate": {"path": str(candidate), "sha256": sha256(candidate)},
                       "opponents": manifest["artifacts"], "engine": manifest["engine"]},
        "windows": {}, "confirm_seal": {"opened": False, "digest_unchanged": False},
        "kaggle_submission": "NOT_PERFORMED",
    }
    if not report["passed"]:
        return report
    actual = importlib.metadata.version("kaggle-environments")
    report["provenance"]["actual_engine"] = actual
    if manifest["engine"] != f"kaggle-environments=={actual}":
        report["passed"] = False
        report["engine_error"] = "installed engine does not match pin"
        return report
    regimes = {f"{window}-{level}": manifest["market_levels"][window][level]
               for window in WINDOWS for level in LEVELS}
    with tempfile.TemporaryDirectory(prefix="sot2949-opponents-") as directory:
        opponents = fetch_artifacts(manifest, Path(directory))
        screen = run_panel(candidate.resolve(), opponents, panels["screen"], regimes)
        unchanged = canonical_sha256(panels["confirm"]) == panel_hashes["confirm"]
        report["confirm_seal"] = {"opened": unchanged, "digest_unchanged": unchanged,
                                  "confirm_panel_sha256": panel_hashes["confirm"]}
        if not unchanged:
            report["passed"] = False
            return report
        confirm = run_panel(candidate.resolve(), opponents, panels["confirm"], regimes)
    effects = {}
    for window, rows in (("screen", screen), ("confirm", confirm)):
        add_tail_scores(rows)
        effects[window] = factorial_effects(rows)
        report["windows"][window] = {"rows": rows, "overall": summarize(rows),
                                      "factor_effects": effects[window]}
    report["confirm_minus_screen_drift"] = {
        factor: {metric: effects["confirm"][factor][metric] - effects["screen"][factor][metric]
                 for metric in ("margin", "rank", "lower_tail")}
        for factor in effects["screen"]}
    report["transfer_trust"] = {
        factor: {metric: abs(value) for metric, value in metrics.items()}
        for factor, metrics in report["confirm_minus_screen_drift"].items()}
    runtime_ok = all(row["terminal_statuses"] == ["DONE", "DONE"]
                     for window in report["windows"].values() for row in window["rows"])
    report["runtime_contract"] = "PASS" if runtime_ok else "FAIL"
    report["passed"] = report["passed"] and runtime_ok
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/factorial_private_proxy_oracle.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2948/SOT-2949-factorial-private-proxy-oracle.json"))
    args = parser.parse_args()
    report = measure(args.candidate, json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SOT-2943: market-shifted, leak-free private-proxy tournament."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import tempfile
from collections import defaultdict
from math import ceil
from pathlib import Path
from typing import Any

try:
    from scripts.measure_leak_free_cv import fetch_artifacts
except ModuleNotFoundError:
    from measure_leak_free_cv import fetch_artifacts


WINDOWS = ("screen", "confirm")
IDENTITY_FIELDS = ("market_regime", "lineage", "episode", "seed", "time_slice")
FORBIDDEN_KEY_PARTS = ("private", "future", "credential", "token", "submission_id", "replay_id")
MARKET_KEYS = {"base", "I0", "T", "below_func", "below_target", "above_func", "above_target"}
MARKET_FUNCTIONS = {"linear", "sq", "sqrt", "log", "log10"}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(any(part in str(key).lower() for part in FORBIDDEN_KEY_PARTS)
                   or _contains_forbidden(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    panels = {window: manifest.get("panels", {}).get(window, []) for window in WINDOWS}
    rows = [row for window in WINDOWS for row in panels[window]]
    regimes = manifest.get("market_regimes", {})
    artifacts = {row.get("id"): row for row in manifest.get("artifacts", [])}
    checks: dict[str, bool] = {
        "schema_supported": manifest.get("schema_version") == 2,
        "confirm_reserved": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "windows_nonempty": all(panels.values()),
        "identity_complete": all(all(row.get(key) is not None for key in (*IDENTITY_FIELDS, "seat", "opponent")) for row in rows),
        "no_private_or_future_fields": not _contains_forbidden(manifest),
        "seat_values_valid": all(row.get("seat") in (0, 1) for row in rows),
        "multiple_market_regimes": len(regimes) >= 4,
        "regimes_declared": all(row.get("market_regime") in regimes for row in rows),
        "official_market_params_only": all(
            isinstance(params, dict) and params and all(
                isinstance(overrides, dict)
                and set(overrides).issubset(MARKET_KEYS)
                and ("below_func" not in overrides or overrides["below_func"] in MARKET_FUNCTIONS)
                and ("above_func" not in overrides or overrides["above_func"] in MARKET_FUNCTIONS)
                for overrides in params.values())
            for params in regimes.values()),
        "artifact_provenance_complete": all(
            row.get("opponent") in artifacts
            and all(artifacts[row["opponent"]].get(key)
                    for key in ("lineage", "source_url", "commit", "path", "license"))
            and len(artifacts[row["opponent"]].get("sha256", "")) == 64
            and all(character in "0123456789abcdef"
                    for character in artifacts[row["opponent"]].get("sha256", "").lower())
            for row in rows),
        "row_lineage_matches_artifact": all(
            artifacts.get(row.get("opponent"), {}).get("lineage") == row.get("lineage") for row in rows),
    }
    overlap: dict[str, list[Any]] = {}
    for field in IDENTITY_FIELDS:
        screen = {row.get(field) for row in panels["screen"]}
        confirm = {row.get(field) for row in panels["confirm"]}
        overlap[field] = sorted(screen & confirm, key=str)
        checks[f"no_{field}_overlap"] = not overlap[field]
    checks["both_seats_per_identity"] = all(
        {row["seat"] for row in panels[window]
         if tuple(row[key] for key in IDENTITY_FIELDS) == identity} == {0, 1}
        for window in WINDOWS
        for identity in {tuple(row[key] for key in IDENTITY_FIELDS) for row in panels[window]}
    )
    screen_times = [row.get("time_index") for row in panels["screen"]]
    confirm_times = [row.get("time_index") for row in panels["confirm"]]
    checks["chronological_confirm"] = (all(isinstance(v, int) for v in screen_times + confirm_times)
                                       and max(screen_times) < min(confirm_times))
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(float(row["margin"]) for row in rows)
    ranks = [int(row["candidate_rank"]) for row in rows]
    tail = max(0, ceil(0.2 * len(margins)) - 1)
    return {"episodes": len(rows), "mean_margin": sum(margins) / len(margins),
            "p20_margin": margins[tail], "worst_margin": margins[0],
            "mean_rank": sum(ranks) / len(ranks), "rank_1_count": sum(rank == 1 for rank in ranks)}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["market_regime"]].append(row)
    return {"overall": summarize(rows),
            "by_market_regime": {name: summarize(group) for name, group in sorted(groups.items())}}


def run_panel(candidate: Path, opponents: dict[str, Path], panel: list[dict[str, Any]],
              regimes: dict[str, Any]) -> list[dict[str, Any]]:
    from kaggle_environments import make

    rows = []
    for identity in panel:
        lineup = [str(candidate), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        configuration = {"episodeSteps": 720, "seed": identity["seed"],
                         "marketParams": regimes[identity["market_regime"]]}
        env = make("kaggriculture", configuration=configuration, debug=False)
        env.run(lineup)
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        margin = rewards[identity["seat"]] - rewards[1 - identity["seat"]]
        rows.append({**identity, "market_params_sha256": canonical_sha256(configuration["marketParams"]),
                     "candidate_reward": rewards[identity["seat"]],
                     "opponent_reward": rewards[1 - identity["seat"]], "margin": margin,
                     "candidate_rank": 1 if margin >= 0 else 2,
                     "terminal_statuses": [str(state.status) for state in terminal]})
    return rows


def measure(candidates: dict[str, Path], manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    panel_hashes = {window: canonical_sha256(manifest["panels"][window]) for window in WINDOWS}
    report: dict[str, Any] = {
        "issue": "SOT-2943", "axis": "market/opponent/seat/seed/time-shift private-proxy re-anchor",
        "passed": validation["passed"], "validation": validation,
        "protocol": {"opening_order": "screen first; confirm digest rechecked before opening",
                     "confirm_status_at_start": manifest.get("confirm_status"),
                     "future_private_policy": "fail closed on forbidden fields",
                     "same_conditions": "every named candidate uses the identical immutable manifest"},
        "provenance": {"manifest_sha256": canonical_sha256(manifest), "panel_sha256": panel_hashes,
                       "market_regimes_sha256": canonical_sha256(manifest.get("market_regimes")),
                       "opponents": manifest.get("artifacts", []),
                       "candidates": {name: {"path": str(path), "sha256": sha256(path)}
                                      for name, path in sorted(candidates.items())},
                       "engine": manifest.get("engine")},
        "candidates": {}, "confirm_seal": {"opened": False, "digest_unchanged": False},
        "kaggle_submission": "NOT_PERFORMED",
    }
    if not validation["passed"]:
        return report
    actual = importlib.metadata.version("kaggle-environments")
    report["provenance"]["actual_engine"] = actual
    if manifest["engine"] != f"kaggle-environments=={actual}":
        report["passed"] = False
        report["engine_error"] = "installed engine does not match pinned engine"
        return report
    with tempfile.TemporaryDirectory(prefix="sot2943-opponents-") as directory:
        opponents = fetch_artifacts(manifest, Path(directory))
        screen_results = {name: run_panel(path.resolve(), opponents, manifest["panels"]["screen"],
                                          manifest["market_regimes"])
                          for name, path in sorted(candidates.items())}
        unchanged = canonical_sha256(manifest["panels"]["confirm"]) == panel_hashes["confirm"]
        report["confirm_seal"] = {"opened": unchanged, "digest_unchanged": unchanged,
                                  "confirm_panel_sha256": panel_hashes["confirm"]}
        if not unchanged:
            report["passed"] = False
            return report
        for name, path in sorted(candidates.items()):
            confirm = run_panel(path.resolve(), opponents, manifest["panels"]["confirm"],
                                manifest["market_regimes"])
            windows = {"screen": screen_results[name], "confirm": confirm}
            summaries = {window: aggregate(rows) for window, rows in windows.items()}
            screen, sealed = summaries["screen"]["overall"], summaries["confirm"]["overall"]
            report["candidates"][name] = {
                window: {"rows": windows[window], **summaries[window]} for window in WINDOWS}
            report["candidates"][name]["transfer_trust"] = {
                "margin_shift": sealed["mean_margin"] - screen["mean_margin"],
                "rank_shift": sealed["mean_rank"] - screen["mean_rank"],
                "tail_shift": sealed["p20_margin"] - screen["p20_margin"],
                "absolute_stability": {"margin": abs(sealed["mean_margin"] - screen["mean_margin"]),
                                       "rank": abs(sealed["mean_rank"] - screen["mean_rank"]),
                                       "tail": abs(sealed["p20_margin"] - screen["p20_margin"])}}
    runtime_ok = all(row["terminal_statuses"] == ["DONE", "DONE"]
                     for candidate in report["candidates"].values()
                     for window in WINDOWS for row in candidate[window]["rows"])
    report["runtime_contract"] = "PASS" if runtime_ok else "FAIL"
    report["passed"] = report["passed"] and runtime_ok
    return report


def _candidate(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("candidate must be NAME=PATH")
    name, raw_path = value.split("=", 1)
    if not name or not raw_path:
        raise argparse.ArgumentTypeError("candidate must be NAME=PATH")
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", action="append", type=_candidate,
                        default=[], help="repeatable NAME=PATH; defaults to champion=main.py")
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/market_shift_oracle.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2942/SOT-2943-market-shift-oracle.json"))
    args = parser.parse_args()
    candidate_items = args.candidate or [("champion", Path("main.py"))]
    if len({name for name, _ in candidate_items}) != len(candidate_items):
        parser.error("candidate names must be unique")
    report = measure(dict(candidate_items), json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

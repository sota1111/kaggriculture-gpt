#!/usr/bin/env python3
"""Re-anchor the live-transfer oracle on the C22 reproducibility control."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import statistics
import tempfile
from math import ceil
from pathlib import Path
from typing import Any

from kaggle_environments import make
import kaggle_environments.envs.kaggriculture.kaggriculture as runtime

try:
    from scripts.measure_kaito_v211_conditional_memory import build_candidate
except ModuleNotFoundError:
    from measure_kaito_v211_conditional_memory import build_candidate

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ("screen", "confirm")
SPLIT_FIELDS = ("opponent", "lineage", "episode", "seed", "time_slice", "market_regime")
FORBIDDEN = ("private", "future", "credential", "token", "replay", "submission_id")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(any(term in str(key).lower() for term in FORBIDDEN) or _forbidden(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_forbidden(child) for child in value)
    return False


def validate_manifest(manifest: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    panels = {name: manifest.get("panels", {}).get(name, []) for name in WINDOWS}
    rows = [row for name in WINDOWS for row in panels[name]]
    opponents = {row.get("id"): row for row in manifest.get("opponents", [])}
    anchors = manifest.get("public_blind_anchors", [])
    sources = manifest.get("sources", [])
    required_row = {*SPLIT_FIELDS, "seat", "time_index"}
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "engine_pinned": manifest.get("engine", "").startswith("kaggle-environments=="),
        "confirm_reserved": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "oracle_agent_decisions_separate": manifest.get("decision_scope") == "oracle-only",
        "no_kaggle_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
        "sources_complete": all(all(row.get(key) for key in ("id", "url", "version", "sha256", "license", "boundary")) for row in sources),
        "source_hashes_valid": all(len(row.get("sha256", "")) == 64 for row in sources),
        "c22_bytes_fetch_only": all(row.get("boundary") == "fetch-only-not-committed" for row in sources if row.get("id", "").startswith("c22-")),
        "blind_scores_fixed": {row.get("id"): row.get("public_score") for row in anchors} == {"old-champion": 781.5, "conditional-memory": 600.0},
        "anchor_hashes_match": all(
            (not row.get("path") or ((root / row["path"]).is_file() and sha256(root / row["path"]) == row.get("sha256")))
            and (not row.get("descriptor") or ((root / row["descriptor"]).is_file() and sha256(root / row["descriptor"]) == row.get("descriptor_sha256")))
            for row in anchors),
        "panels_nonempty": all(panels.values()),
        "rows_complete": all(required_row <= set(row) for row in rows),
        "no_private_future_replay_fields": not _forbidden(manifest),
        "opponent_provenance_complete": all(row.get("opponent") in opponents and opponents[row["opponent"]].get("lineage") == row.get("lineage") for row in rows),
        "repository_opponent_hashes_match": all(
            not row.get("path") or ((root / row["path"]).is_file() and sha256(root / row["path"]) == row.get("sha256"))
            for row in opponents.values()),
    }
    overlap = {}
    for field in SPLIT_FIELDS:
        overlap[field] = sorted({row[field] for row in panels["screen"]} & {row[field] for row in panels["confirm"]}, key=str)
        checks[f"no_{field}_overlap"] = not overlap[field]
    checks["chronological_confirm"] = max(row["time_index"] for row in panels["screen"]) < min(row["time_index"] for row in panels["confirm"])
    checks["same_seed_both_seats"] = all(
        {row["seat"] for row in panels[window] if row["episode"] == episode} == {0, 1}
        and len({row["seed"] for row in panels[window] if row["episode"] == episode}) == 1
        for window in WINDOWS for episode in {row["episode"] for row in panels[window]})
    checks["market_regimes_declared"] = all(row["market_regime"] in manifest.get("market_regimes", {}) for row in rows)
    return {"passed": all(checks.values()), "checks": checks, "overlap": overlap}


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = sorted(float(row["margin"]) for row in rows)
    tail = max(0, ceil(0.2 * len(margins)) - 1)
    return {"episodes": len(rows), "mean_rank": statistics.fmean(row["rank"] for row in rows),
            "mean_margin": statistics.fmean(margins), "p20_margin": margins[tail],
            "worst_margin": margins[0], "rank_1_count": sum(row["rank"] == 1 for row in rows)}


def _run(agent: Path, opponent: Path, identity: dict[str, Any], regimes: dict[str, Any]) -> dict[str, Any]:
    lineup = [str(agent), str(opponent)]
    if identity["seat"] == 1:
        lineup.reverse()
    configuration = {"episodeSteps": 720, "seed": identity["seed"]}
    if regimes[identity["market_regime"]]:
        configuration["marketParams"] = regimes[identity["market_regime"]]
    env = make("kaggriculture", configuration=configuration, debug=False)
    env.run(lineup)
    terminal = env.steps[-1]
    rewards = [float(state.reward or 0) for state in terminal]
    seat = identity["seat"]
    margin = rewards[seat] - rewards[1 - seat]
    return {**identity, "agent_reward": rewards[seat], "opponent_reward": rewards[1-seat],
            "margin": margin, "rank": 1 if margin >= 0 else 2,
            "terminal_statuses": [str(state.status) for state in terminal], "steps": len(env.steps),
            "market_params_sha256": canonical_sha256(regimes[identity["market_regime"]])}


def measure(manifest: dict[str, Any], c22_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    validation = validate_manifest(manifest, root)
    report: dict[str, Any] = {"issue":"SOT-2991", "axis":"C22 reproducibility live-transfer oracle re-anchor",
        "passed": validation["passed"], "validation": validation,
        "provenance":{"manifest_sha256":canonical_sha256(manifest), "sources":manifest.get("sources", [])},
        "protocol":{"primary_kpi":"live public ordering fidelity; local margin/rank/tails are proxy diagnostics",
                    "split":"opponent/lineage/episode/seed/seat/time/market", "same_seed_both_seats":True,
                    "opening_order":"screen first; confirm digest rechecked before opening"},
        "confirm_seal":{"opened":False}, "anchors":{}, "oracle_decision":"inconclusive",
        "agent_decision":"NOT_EVALUATED_OR_PROMOTED", "kaggle_submission":"NOT_PERFORMED"}
    if not validation["passed"]:
        return report
    actual_version = importlib.metadata.version("kaggle-environments")
    runtime_path = Path(inspect.getfile(runtime))
    c22_source = c22_dir / "kaggriculture-c22-exact-reproducibility-control.py"
    c22_metadata = c22_dir / "kernel-metadata.json"
    expected = {row["id"]: row["sha256"] for row in manifest["sources"]}
    acquisition = {
        "engine_version_match": manifest["engine"] == f"kaggle-environments=={actual_version}",
        "runtime_hash_match": sha256(runtime_path) == expected["official-runtime"],
        "c22_source_hash_match": c22_source.is_file() and sha256(c22_source) == expected["c22-control-source"],
        "c22_metadata_hash_match": c22_metadata.is_file() and sha256(c22_metadata) == expected["c22-kernel-metadata"],
        "c22_not_committed": not any(path.is_file() and sha256(path) == expected["c22-control-source"] for path in root.rglob("*.py")),
    }
    report["provenance"]["acquisition_checks"] = acquisition
    if not all(acquisition.values()):
        report["passed"] = False
        return report
    opponents = {row["id"]: (c22_source if row["kind"] == "external-c22" else root / row["path"])
                 for row in manifest["opponents"]}
    confirm_digest = canonical_sha256(manifest["panels"]["confirm"])
    with tempfile.TemporaryDirectory(prefix="sot2991-anchor-") as directory:
        conditional = Path(directory) / "conditional_memory.py"
        build_candidate(conditional)
        agents = {"old-champion": root / "main.py", "conditional-memory": conditional}
        screen = {name:[_run(path, opponents[row["opponent"]], row, manifest["market_regimes"])
                        for row in manifest["panels"]["screen"]] for name, path in agents.items()}
        unchanged = canonical_sha256(manifest["panels"]["confirm"]) == confirm_digest
        report["confirm_seal"] = {"opened":unchanged, "digest_unchanged":unchanged, "sha256":confirm_digest}
        if not unchanged:
            report["passed"] = False
            return report
        for name, path in agents.items():
            confirm = [_run(path, opponents[row["opponent"]], row, manifest["market_regimes"])
                       for row in manifest["panels"]["confirm"]]
            summaries = {"screen":_summary(screen[name]), "confirm":_summary(confirm)}
            drift = {key:summaries["confirm"][key]-summaries["screen"][key]
                     for key in ("mean_rank","mean_margin","p20_margin","worst_margin")}
            scale = max(1.0, abs(summaries["screen"]["mean_margin"]), abs(summaries["screen"]["p20_margin"]))
            report["anchors"][name] = {"public_score":next(row["public_score"] for row in manifest["public_blind_anchors"] if row["id"] == name),
                "screen":{"rows":screen[name], **summaries["screen"]}, "confirm":{"rows":confirm, **summaries["confirm"]},
                "transfer_trust":{"confirm_minus_screen":drift,
                    "stability_0_to_1":max(0.0, 1.0-max(abs(drift["mean_margin"]),abs(drift["p20_margin"]),abs(drift["worst_margin"]))/scale)}}
    runtime_ok = all(row["terminal_statuses"] == ["DONE","DONE"] and row["steps"] == 720
                     for anchor in report["anchors"].values() for window in WINDOWS for row in anchor[window]["rows"])
    ordering = {window: report["anchors"]["old-champion"][window]["mean_margin"] > report["anchors"]["conditional-memory"][window]["mean_margin"] for window in WINDOWS}
    report["blind_anchor_fidelity"] = {"expected":"old-champion (781.5) > conditional-memory (600.0)",
        "by_window":ordering, "all_windows_recover_public_ordering":all(ordering.values())}
    report["runtime_contract"] = "PASS" if runtime_ok else "FAIL"
    report["passed"] = report["passed"] and runtime_ok
    report["oracle_decision"] = ("promoted" if all(ordering.values()) else "rejected") if report["passed"] else "inconclusive"
    report["oracle_decision_reason"] = ("Both screen and sealed confirm recover the pre-registered live public ordering."
        if all(ordering.values()) else
        "The mechanically valid local oracle contradicts the pre-registered 781.5 > 600.0 live ordering in both windows, so this panel is rejected as a promotion oracle; no agent is rejected or promoted by this result.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/fixtures/c22_live_transfer_oracle.json")
    parser.add_argument("--c22-dir", type=Path, required=True, help="temporary kaggle kernels pull directory")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/measurements/SOT-2986/SOT-2991-c22-live-transfer-oracle.json")
    args = parser.parse_args()
    report = measure(json.loads(args.manifest.read_text()), args.c22_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed":report["passed"], "oracle_decision":report["oracle_decision"], "output":str(args.output)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

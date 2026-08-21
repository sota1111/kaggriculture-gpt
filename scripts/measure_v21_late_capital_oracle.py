#!/usr/bin/env python3
"""Fresh, leak-free closed-loop oracle for the Seyamalam V21 latch (SOT-2867)."""
from __future__ import annotations
import argparse, hashlib, json, tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
try:
    from scripts.evaluate import load_agent, run_episode
    from scripts.measure_leak_free_cv import canonical_sha256, fetch_artifacts
except ModuleNotFoundError:
    from evaluate import load_agent, run_episode
    from measure_leak_free_cv import canonical_sha256, fetch_artifacts

WINDOWS = ("screen", "confirm")
FORBIDDEN_KEYS = {"private", "future", "future_actions", "future_prices", "credentials", "replay", "replay_bytes", "recorded_actions", "weights", "reward"}

def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(FORBIDDEN_KEYS & set(value)) or any(_contains_forbidden(v) for v in value.values())
    return isinstance(value, list) and any(_contains_forbidden(v) for v in value)

def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    panels = {name: manifest.get("panels", {}).get(name, []) for name in WINDOWS}
    artifacts = {row.get("id"): row for row in manifest.get("artifacts", [])}
    required = {"entity", "episode", "seed", "time", "seat", "opponent"}
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "panels_nonempty": all(panels.values()),
        "required_fields": all(required <= set(row) for rows in panels.values() for row in rows),
        "public_manifest_only": not _contains_forbidden(manifest),
        "artifacts_pinned": bool(artifacts) and all(row.get("source_url") == "https://github.com/Seyamalam/Kaggriculture" and len(row.get("commit", "")) == 40 and len(row.get("sha256", "")) == 64 and row.get("license") == "MIT" and row.get("redistribution") == "fetch-only" for row in artifacts.values()),
        "opponents_resolve": all(row.get("opponent") in artifacts for rows in panels.values() for row in rows),
        "both_seats_each_entity": all({row.get("seat") for row in rows if row.get("entity") == entity} == {0, 1} for rows in panels.values() for entity in {row.get("entity") for row in rows}),
        "no_committed_sensitive_artifacts": manifest.get("sensitive_artifacts") == "NOT_COMMITTED",
        "closed_loop": manifest.get("evaluation") == "fresh-local-closed-loop",
        "screen_before_confirm": manifest.get("confirm_policy") == "consume-only-after-screen-pass",
    }
    for field in ("entity", "episode", "seed", "time"):
        checks[f"{field}_holdout"] = {row.get(field) for row in panels["screen"]}.isdisjoint({row.get(field) for row in panels["confirm"]})
    checks["strict_temporal_order"] = bool(panels["screen"] and panels["confirm"]) and max(row["time"] for row in panels["screen"]) < min(row["time"] for row in panels["confirm"])
    return {"passed": all(checks.values()), "checks": checks}

def _panel(champion: Any, opponents: dict[str, Any], fixture: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    episodes = []
    for row in rows:
        champion_result = asdict(run_episode(champion, fixture, row["seed"]))
        opponent_result = asdict(run_episode(opponents[row["opponent"]], fixture, row["seed"]))
        margin = champion_result["reward"] - opponent_result["reward"]
        episodes.append({"identity": {key: row[key] for key in ("entity", "episode", "seed", "time", "seat")}, "opponent": row["opponent"], "champion": champion_result, "opponent_result": opponent_result, "champion_margin": margin, "champion_rank": 1 if margin >= 0 else 2})
    return {"episodes": episodes, "both_seats": sorted({row["seat"] for row in rows}), "summary": {"episodes": len(episodes), "mean_champion_margin": sum(row["champion_margin"] for row in episodes) / len(episodes), "worst_champion_margin": min(row["champion_margin"] for row in episodes), "mean_champion_rank": sum(row["champion_rank"] for row in episodes) / len(episodes), "invalid_actions": sum(row["champion"]["invalid_actions"] for row in episodes), "contract_violations": sum(row["champion"]["contract_violations"] for row in episodes)}}

def _screen_passed(panel: dict[str, Any]) -> bool:
    return panel["both_seats"] == [0, 1] and panel["summary"]["invalid_actions"] == 0 and panel["summary"]["contract_violations"] == 0

def measure(policy: Path, fixture: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    provenance = {"source_url": "https://github.com/Seyamalam/Kaggriculture", "source_commit": "8b8c421eb10634c756583ce10c75189f50c83a72", "source_license": "MIT", "source_main_sha256": "0cd14b653102d276c4f902fa3b8c6bd81d869b8ab64c422cb881b9d2346ec639", "champion_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(), "manifest_sha256": canonical_sha256(manifest)}
    if not validation["passed"]:
        return {"issue": "SOT-2867", "passed": False, "validation": validation, "screen": {"skipped": True}, "confirm": {"skipped": True}, "provenance": provenance, "result": "inconclusive", "kaggle_submission": "NOT_PERFORMED"}
    with tempfile.TemporaryDirectory(prefix="sot2867-v21-") as directory:
        paths = fetch_artifacts(manifest, Path(directory))
        opponents = {key: load_agent(value) for key, value in paths.items()}
        champion = load_agent(policy)
        screen = _panel(champion, opponents, fixture, manifest["panels"]["screen"])
        if not _screen_passed(screen):
            return {"issue": "SOT-2867", "passed": False, "validation": validation, "screen": screen, "confirm": {"skipped": True, "reason": "screen gate failed"}, "provenance": provenance, "result": "inconclusive", "kaggle_submission": "NOT_PERFORMED"}
        confirm = _panel(champion, opponents, fixture, manifest["panels"]["confirm"])
    report = {"issue": "SOT-2867", "axis": "Seyamalam V21 one-time step-577 late capital latch oracle", "passed": _screen_passed(confirm), "result": "inconclusive", "validation": validation, "screen": screen, "confirm": confirm, "provenance": provenance, "v21_delta": {"reference": "V20 ended the recovery overlay at step 577", "change": "V21 extends the overlay to step 718 but latches once at step 577 and abstains only when rival_money-own_money <= -5000", "inputs": ["step", "player", "both farms' public money"]}, "sensitive_artifacts": "NOT_COMMITTED", "kaggle_submission": "NOT_PERFORMED"}
    report["deterministic_report_sha256"] = canonical_sha256(report)
    return report

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("main.py")); parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json")); parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/v21_late_capital_oracle.json")); parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2865/SOT-2867-v21-late-capital-oracle.json"))
    args = parser.parse_args(); report = measure(args.policy.resolve(), json.loads(args.fixture.read_text()), json.loads(args.manifest.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "result": report["result"], "confirm_skipped": report["confirm"].get("skipped", False)}, sort_keys=True)); return 0 if report["passed"] else 1
if __name__ == "__main__": raise SystemExit(main())

#!/usr/bin/env python3
"""Measure the GzmCR-inspired clean-room foundation against historical control."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import tempfile
from collections import Counter
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import canonical_sha256, fetch_artifacts
    from scripts.measure_reactive_optimal_task import compare, run, summarize
except ModuleNotFoundError:
    from measure_leak_free_cv import canonical_sha256, fetch_artifacts
    from measure_reactive_optimal_task import compare, run, summarize

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/gzmcr-cleanroom/agent.py"
SOURCE = ROOT / "candidates/gzmcr-cleanroom/source.json"
FIXTURE = ROOT / "tests/fixtures/gzmcr_cleanroom.json"
OUTPUT = ROOT / "docs/measurements/SOT-2990/SOT-2990-gzmcr-cleanroom.json"
CONTROL = ROOT / "main.py"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_candidate():
    spec = importlib.util.spec_from_file_location("gzmcr_cleanroom", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(fixture, source):
    screen, confirm = fixture["screen"], fixture["confirm"]
    tree = ast.parse(CANDIDATE.read_text())
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
    imports |= {node.module.split(".")[0] for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module}
    split = ("opponent", "episode", "seed", "time_index")
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.7",
        "commit_license_hash_recorded": all(source.get(key) for key in
            ("source_commit", "source_main_sha256", "historical_control_sha256", "license", "license_boundary")),
        "unlicensed_clean_room_boundary": source.get("license") == "UNDECLARED"
            and "upstream main.py source code" in source.get("excluded", []),
        "candidate_hash_pinned": sha256(CANDIDATE) == source.get("candidate_sha256"),
        "stdlib_only": imports <= {"collections"},
        "default_off_independent": source.get("default_enabled") is False
            and "gzmcr-cleanroom" not in CONTROL.read_text(),
        "same_seed_both_seats": all({row["seat"] for row in panel if row["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {row["seed"] for row in panel}),
        "opponent_episode_seed_time_disjoint": all(
            {row[key] for row in screen}.isdisjoint({row[key] for row in confirm}) for key in split),
        "composite_identities_disjoint": {tuple(row[k] for k in (*split, "seat")) for row in screen}
            .isdisjoint({tuple(row[k] for k in (*split, "seat")) for row in confirm}),
        "chronological_confirm": max(row["time_index"] for row in screen) < min(row["time_index"] for row in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def main():
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate(fixture, source)
    module = load_candidate()
    malformed = module.agent({"step": "invalid", "farms": None})
    report = {
        "issue": "SOT-2990", "axis": "GzmCR role-planned clean-room independent whole-agent",
        "source": source, "checks": checks,
        "historical_control": {"path": "main.py", "sha256": sha256(CONTROL),
            "upstream_v000_sha256": source["historical_control_sha256"], "modified": False},
        "candidate": {"path": str(CANDIDATE.relative_to(ROOT)), "sha256": sha256(CANDIDATE)},
        "default_enabled": False, "kaggle_submission": "NOT_PERFORMED",
        "invalid_observation_contract": "PASS" if isinstance(malformed, dict)
            and set(malformed) == {"farmer", "hands", "market"} else "FAIL",
        "actual_engine": importlib.metadata.version("kaggle-environments"),
    }
    if fixture["engine"] != f"kaggle-environments=={report['actual_engine']}" or not all(checks.values()):
        report.update({"passed": False, "decision": "inconclusive", "reason": "preflight failed"})
    else:
        manifest = json.loads((ROOT / fixture["opponent_manifest"]).read_text())
        with tempfile.TemporaryDirectory(prefix="sot2990-") as directory:
            opponents = fetch_artifacts(manifest, Path(directory))
            for window in ("screen", "confirm"):
                control_rows = run(str(CONTROL), opponents, fixture[window])
                candidate_rows = run(module.agent, opponents, fixture[window])
                report[window] = {"control_rows": control_rows, "candidate_rows": candidate_rows,
                    "control": summarize(control_rows), "candidate": summarize(candidate_rows)}
                report[window]["gate"] = compare(report[window]["control"], report[window]["candidate"])
        trace = module.trace_snapshot()
        report["role_work_intervention_log"] = trace
        fingerprints = {window: {side: dict(Counter(name for row in report[window][side + "_rows"]
            for name, count in row["action_families"].items() for _ in range(count)))
            for side in ("control", "candidate")} for window in ("screen", "confirm")}
        report["action_family_fingerprint"] = {"counts": fingerprints,
            "sha256": canonical_sha256(fingerprints),
            "diverged_from_control": any(fingerprints[w]["control"] != fingerprints[w]["candidate"]
                                          for w in ("screen", "confirm"))}
        rows = [row for w in ("screen", "confirm") for side in ("control", "candidate")
                for row in report[w][side + "_rows"]]
        contract = all(row["statuses"] == ["DONE", "DONE"] and row["steps"] == 720
            and row["runtime_seconds"] < fixture["episode_timeout_seconds"] and row["invalid_actions"] == 0
            for row in rows)
        fired = trace["calls"] > 0 and sum(trace["roles"].values()) > 0 and sum(trace["work"].values()) > 0
        promoted = report["screen"]["gate"]["passed"] and report["confirm"]["gate"]["passed"]
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        report["decision"] = "promoted-independent-hedge" if promoted else (
            "rejected-candidate-inactive" if fired else "inconclusive")
        report["passed"] = contract and fired and report["action_family_fingerprint"]["diverged_from_control"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

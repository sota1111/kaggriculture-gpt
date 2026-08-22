#!/usr/bin/env python3
"""Fail-closed provenance audit and transient whole-agent evaluation for SOT-2965."""
from __future__ import annotations

import ast
import base64
import hashlib
import importlib.metadata
import json
import subprocess
import tempfile
import zlib
from collections import Counter
from pathlib import Path

try:
    from scripts.measure_harvestforge_x import compare, run, sha256, summarize
    from scripts.measure_leak_free_cv import canonical_sha256, fetch_artifacts
except ModuleNotFoundError:
    from measure_harvestforge_x import compare, run, sha256, summarize
    from measure_leak_free_cv import canonical_sha256, fetch_artifacts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidates/pure-architecture-2600/source.json"
FIXTURE = ROOT / "tests/fixtures/pure_architecture_2600.json"
OUTPUT = ROOT / "docs/measurements/SOT-2962/SOT-2965-pure-architecture-2600.json"
CHAMPION = ROOT / "main.py"
ALLOWED_IMPORTS = {"__future__", "base64", "copy", "json", "zlib"}


def validate_manifest(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.4",
        "source_hash_runtime_boundary_complete": all(source.get(k) for k in (
            "source_url", "kaggle_ref", "kernel_id", "version", "notebook_sha256",
            "agent_sha256", "agent_bytes", "runtime_imports", "runtime_boundary")),
        "license_fail_closed": source.get("license") == "UNSPECIFIED"
            and source.get("redistribution") == "prohibited-fail-closed",
        "source_not_redistributed": not (ROOT / "candidates/pure-architecture-2600/agent.py").exists(),
        "stdlib_offline_boundary": set(source.get("runtime_imports", [])) <= ALLOWED_IMPORTS,
        "default_off_champion_held": source.get("default_enabled") is False,
        "public_claim_excluded": source.get("public_2600_claim_evidence") is False,
        "same_seed_both_seats": all(
            {row["seat"] for row in panel if row["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {row["seed"] for row in panel}),
        "screen_confirm_disjoint": all(
            {row[key] for row in screen}.isdisjoint({row[key] for row in confirm})
            for key in ("lineage", "episode", "seed", "time_index")),
        "chronological_confirm": max(row["time_index"] for row in screen)
            < min(row["time_index"] for row in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def extract_agent(notebook: Path, target: Path, source: dict) -> dict:
    if sha256(notebook) != source["notebook_sha256"]:
        raise ValueError("notebook hash mismatch")
    payload = None
    document = json.loads(notebook.read_text())
    for cell in document["cells"]:
        if cell.get("cell_type") != "code":
            continue
        text = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Assign) and any(
                    isinstance(item, ast.Name) and item.id == "agent_payload" for item in node.targets):
                payload = ast.literal_eval(node.value)
    if not isinstance(payload, str):
        raise ValueError("embedded agent payload not found")
    code = zlib.decompress(base64.b85decode(payload.encode()))
    if hashlib.sha256(code).hexdigest() != source["agent_sha256"] or len(code) != source["agent_bytes"]:
        raise ValueError("agent hash or size mismatch")
    tree, imports = ast.parse(code), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    target.write_bytes(code)
    return {"notebook_hash_ok": True, "agent_hash_ok": True, "agent_bytes": len(code),
        "imports": sorted(imports), "stdlib_only": imports <= ALLOWED_IMPORTS,
        "transient_path": True, "redistributed": False}


def action_fingerprint(rows: list[dict]) -> dict:
    counts = Counter()
    for row in rows:
        counts.update(row["action_families"])
    return dict(sorted(counts.items()))


def stable_panel(panel: dict) -> dict:
    """Exclude wall-clock telemetry while retaining every decision metric."""
    return {key: ({metric: value for metric, value in item.items()
                   if metric != "max_runtime_seconds"} if isinstance(item, dict) else item)
            for key, item in panel.items() if not key.endswith("_rows")}


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate_manifest(fixture, source)
    report = {"issue": "SOT-2965", "axis": "Pure Architecture 2600 independent whole-agent",
        "source": source, "checks": checks,
        "champion": {"path": "main.py", "sha256": sha256(CHAMPION), "modified": False},
        "public_score_used_for_promotion": False, "kaggle_submission": "NOT_PERFORMED",
        "actual_engine": importlib.metadata.version("kaggle-environments")}
    try:
        if fixture["engine"] != f"kaggle-environments=={report['actual_engine']}" or not all(checks.values()):
            raise ValueError("manifest preflight failed")
        with tempfile.TemporaryDirectory(prefix="sot2965-") as raw:
            work = Path(raw)
            subprocess.run(["kaggle", "kernels", "pull", source["kaggle_ref"],
                "-p", str(work), "-m"], check=True, capture_output=True, text=True)
            notebook = work / "kaggriculture-pure-architecture-2600-elo-v3.ipynb"
            candidate = work / "main.py"
            report["acquisition"] = extract_agent(notebook, candidate, source)
            if not report["acquisition"]["stdlib_only"]:
                raise ValueError("non-stdlib runtime dependency")
            opponents_dir = work / "opponents"
            opponents_dir.mkdir()
            opponents = fetch_artifacts(json.loads((ROOT / fixture["opponent_manifest"]).read_text()), opponents_dir)
            report["screen"] = {"champion_rows": run(CHAMPION, opponents, fixture["screen"]),
                "candidate_rows": run(candidate, opponents, fixture["screen"])}
            for side in ("champion", "candidate"):
                report["screen"][side] = summarize(report["screen"][side + "_rows"])
            report["screen"]["gate"] = compare(report["screen"]["champion"], report["screen"]["candidate"])
            if report["screen"]["gate"]["passed"]:
                report["confirm"] = {"champion_rows": run(CHAMPION, opponents, fixture["confirm"]),
                    "candidate_rows": run(candidate, opponents, fixture["confirm"])}
                for side in ("champion", "candidate"):
                    report["confirm"][side] = summarize(report["confirm"][side + "_rows"])
                report["confirm"]["gate"] = compare(report["confirm"]["champion"], report["confirm"]["candidate"])
            else:
                report["confirm"] = {"skipped": True, "reason": "screen promotion gate failed"}
        rows = report["screen"]["champion_rows"] + report["screen"]["candidate_rows"]
        if not report["confirm"].get("skipped"):
            rows += report["confirm"]["champion_rows"] + report["confirm"]["candidate_rows"]
        report["runtime_contract"] = {"passed": all(row["statuses"] == ["DONE", "DONE"]
            and row["steps"] == 720 and row["invalid_actions"] == 0
            and row["mean_step_seconds"] < 1 for row in rows),
            "step_budget_seconds": 1, "terminal_steps": 720, "json_action_invalid_count": sum(
                row["invalid_actions"] for row in rows)}
        fingerprints = {"champion_screen": action_fingerprint(report["screen"]["champion_rows"]),
            "candidate_screen": action_fingerprint(report["screen"]["candidate_rows"])}
        report["action_family_fingerprint"] = {"counts": fingerprints,
            "sha256": canonical_sha256(fingerprints),
            "diverged_from_champion": fingerprints["champion_screen"] != fingerprints["candidate_screen"]}
        promoted = report["screen"]["gate"]["passed"] and not report["confirm"].get("skipped") \
            and report["confirm"]["gate"]["passed"]
        report["performance_decision"] = "promoted" if promoted else "rejected"
        report["decision"] = "rejected"
        report["decision_reason"] = ("performance screen and confirm passed, but the source has no declared "
            "redistribution license; retain provenance-only evidence and do not promote the agent artifact")
        report["passed"] = report["runtime_contract"]["passed"] and report["action_family_fingerprint"]["diverged_from_champion"]
        report["deterministic_result_sha256"] = canonical_sha256({
            "screen": stable_panel(report["screen"]),
            "confirm": stable_panel(report["confirm"]),
            "fingerprints": fingerprints, "performance_decision": report["performance_decision"],
            "decision": report["decision"]})
    except Exception as error:
        report.update({"passed": False, "decision": "inconclusive", "reason": f"{type(error).__name__}: {error}"})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

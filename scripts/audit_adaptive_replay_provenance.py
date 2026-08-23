#!/usr/bin/env python3
"""Validate the fail-closed Adaptive Replay provenance boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidates/adaptive-replay-audit/source.json"
OUTPUT = ROOT / "docs/measurements/SOT-3032/adaptive-replay-provenance.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(source: dict, source_dir: Path | None = None) -> dict[str, bool]:
    structure = source.get("structure", {})
    forbidden_names = {
        source.get("notebook_filename"), "agent.py", "main.py", "actions.json",
        "replay.json", "submission.tar.gz",
    }
    committed_files = {path.name for path in SOURCE.parent.iterdir() if path.is_file()}
    checks = {
        "source_url_version_hash_license_pinned": all(source.get(key) for key in (
            "source_url", "kernel_id", "kernel_version", "kernel_last_run_utc",
            "notebook_sha256", "kernel_metadata_sha256", "embedded_agent_sha256",
            "decoded_action_table_sha256", "license")),
        "license_fails_closed": source.get("license") == "UNDECLARED"
            and source.get("redistribution") == "fetch-only"
            and source.get("verbatim_decision") == "PROHIBITED",
        "fixed_schedule_proven": structure.get("schedule_steps") == 719
            and structure.get("non_pass_steps", 0) >= 690
            and structure.get("decoded_action_table_bytes", 0) >= 100_000,
        "replay_identity_dependencies_proven": len(
            structure.get("replay_identity_dependencies", [])) >= 3,
        "no_private_trace_or_credentials": structure.get(
            "private_trace_or_external_replay_bytes") is False
            and structure.get("credential_or_network_dependency") is False,
        "no_forbidden_artifact_committed": not (committed_files & forbidden_names),
        "no_clean_room_candidate_claim": source.get("clean_room_decision")
            == "NO_STANDALONE_CANDIDATE"
            and source.get("candidate_ablation") == "NOT_APPLICABLE_NO_PORTABLE_CANDIDATE",
        "sealed_confirm_unopened": source.get("sealed_confirm") == "NOT_OPENED_NO_CANDIDATE",
        "incumbent_preserved": source.get("incumbent_modified") is False,
        "no_submission": source.get("kaggle_submission") == "NOT_PERFORMED",
    }
    if source_dir is not None:
        checks["transient_notebook_hash_matches"] = sha256(
            source_dir / source["notebook_filename"]) == source["notebook_sha256"]
        checks["transient_metadata_hash_matches"] = sha256(
            source_dir / "kernel-metadata.json") == source["kernel_metadata_sha256"]
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    source = json.loads(SOURCE.read_text())
    checks = validate(source, args.source_dir)
    report = {
        "issue": "SOT-3032",
        "axis": "Adaptive Replay Agent provenance boundary",
        "decision": "fetch-only-rejected-no-portable-candidate",
        "passed": all(checks.values()),
        "checks": checks,
        "provenance": source,
        "intervention_firing_log": "NOT_APPLICABLE_NO_CANDIDATE",
        "screen": "NOT_RUN_NO_CANDIDATE",
        "sealed_confirm": "NOT_OPENED_NO_CANDIDATE",
        "kaggle_submission": "NOT_PERFORMED",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "passed": report["passed"],
                      "output": str(OUTPUT.relative_to(ROOT))}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

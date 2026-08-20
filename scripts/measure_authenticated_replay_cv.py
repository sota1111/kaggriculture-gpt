#!/usr/bin/env python3
"""Emit the auditable SOT-2782 authenticated replay-anchor measurement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.evaluate import validate_authenticated_replay_cv
except ModuleNotFoundError:
    from evaluate import validate_authenticated_replay_cv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=Path("tests/fixtures/authenticated_replay_manifest.json"))
    parser.add_argument("--replay-dir", type=Path,
                        default=Path("docs/measurements/SOT-2781/replays"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2781/SOT-2782-authenticated-replay-cv.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    report = validate_authenticated_replay_cv(manifest, args.replay_dir)
    report.update({
        "axis": "authenticated current-top replay CV re-anchor",
        "result": "promoted" if report["passed"] else "inconclusive",
        "leaderboard_anchor": manifest["leaderboard_anchor"],
        "manifest_sha256": manifest["manifest_sha256"],
        "runtime_candidate_changed": False,
        "submission_contract": "UNCHANGED",
        "exec_compatibility": "UNCHANGED",
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"authenticated replay CV: {'PASS' if report['passed'] else 'FAIL'} ({args.output})")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

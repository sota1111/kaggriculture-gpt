#!/usr/bin/env python3
"""Build the independent clean-room V111 economic-core agent."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "candidates/lonespear-care-production/agent.py"
OVERLAY = ROOT / "candidates/v111-economic-core/overlay.py"


def build(output: Path) -> dict[str, object]:
    payload = (FOUNDATION.read_text().rstrip() + "\n\n" + OVERLAY.read_text()).encode()
    compile(payload, str(output), "exec")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return {"path": str(output), "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload), "champion_dependency": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

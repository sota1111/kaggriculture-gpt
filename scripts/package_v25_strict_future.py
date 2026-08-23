#!/usr/bin/env python3
"""Build the independent clean-room v25 whole-agent artifact."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "candidates/apache-agent-builder/agent.py"
POLICY = ROOT / "candidates/v25-strict-future-cleanroom/policy.py"
OUTPUT = ROOT / "candidates/v25-strict-future-cleanroom/agent.py"
LICENSE = ROOT / "candidates/v25-strict-future-cleanroom/LICENSE-Apache-2.0.txt"


def build(output=OUTPUT):
    payload = (BASE.read_text().rstrip() + "\n\n" + POLICY.read_text()).encode()
    compile(payload, str(output), "exec")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    LICENSE.write_bytes((BASE.parent / "LICENSE-Apache-2.0.txt").read_bytes())
    return {"path": str(output.relative_to(ROOT)), "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}


if __name__ == "__main__":
    print(build())

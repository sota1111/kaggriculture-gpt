#!/usr/bin/env python3
"""Build the independent clean-room diversified scheduler candidate."""
import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "candidates/diversified-scheduler/policy.py"


def build(output: Path, enabled: bool = False):
    payload = POLICY.read_text()
    if enabled:
        payload = payload.replace("DIVERSIFIED_SCHEDULER = False",
                                  "DIVERSIFIED_SCHEDULER = True", 1)
    encoded = payload.encode()
    compile(encoded, str(output), "exec")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return {"path": str(output), "sha256": hashlib.sha256(encoded).hexdigest(),
            "enabled": enabled, "bytes": len(encoded)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args()
    print(build(args.output, args.enable))


if __name__ == "__main__":
    main()

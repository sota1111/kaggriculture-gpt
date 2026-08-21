#!/usr/bin/env python3
"""Build the independent V16-RC5 clean-room candidate deterministically."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAMPION = ROOT / "main.py"
POLICY = ROOT / "candidates/v16-rc5-portable/policy.py"


def build(output: Path, enabled: bool = False) -> dict[str, object]:
    policy = POLICY.read_text()
    if enabled:
        policy = policy.replace("V16_RC5_PORTABLE = False", "V16_RC5_PORTABLE = True", 1)
    payload = (CHAMPION.read_text().rstrip() + "\n\n" + policy).encode()
    compile(payload, str(output), "exec")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return {"path": str(output), "sha256": hashlib.sha256(payload).hexdigest(),
            "enabled": enabled, "bytes": len(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args()
    print(build(args.output, args.enable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

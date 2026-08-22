#!/usr/bin/env python3
"""Fail-closed extractor for the hash-pinned C95 notebook artifact."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

NOTEBOOK_SHA256 = "cdca09ed40f2c3a8b142791dd2f1b5f3dffc2de4332a153e53da6c63d58e7b5a"
AGENT_SHA256 = "ed8c8420514acb5a96c0d44cfd42a8786e49c7cdc01a0de61d2e6b8997dda87a"
AGENT_BYTES = 133270


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract(notebook: Path) -> bytes:
    raw = notebook.read_bytes()
    if sha256(raw) != NOTEBOOK_SHA256:
        raise ValueError("notebook SHA-256 mismatch")
    document = json.loads(raw)
    assignments = []
    for cell in document.get("cells", []):
        source = cell.get("source", "")
        source = "".join(source) if isinstance(source, list) else source
        if cell.get("cell_type") != "code" or "AGENT_SOURCE" not in source:
            continue
        tree = ast.parse(source)
        assignments.extend(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "AGENT_SOURCE" for target in node.targets)
        )
    if len(assignments) != 1:
        raise ValueError(f"expected one AGENT_SOURCE assignment, found {len(assignments)}")
    value = ast.literal_eval(assignments[0].value)
    artifact = value.encode("utf-8")
    if len(artifact) != AGENT_BYTES or sha256(artifact) != AGENT_SHA256:
        raise ValueError("agent identity mismatch")
    compile(artifact, "c95-agent.py", "exec")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    artifact = extract(args.notebook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(artifact)
    print(json.dumps({"bytes": len(artifact), "sha256": sha256(artifact), "output": str(args.output)}))


if __name__ == "__main__":
    main()

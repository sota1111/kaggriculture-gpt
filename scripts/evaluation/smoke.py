#!/usr/bin/env python3
"""Audit real candidate artifacts against the sealed protocol configuration."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from scripts.evaluation.sealed import (OFFICIAL_ENGINE, EnginePin, SealedProtocol,
                                       validate_engine, validate_protocol)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/current_engine_sealed.json"
OUTPUT = ROOT / "docs/measurements/SOT-3007/current-engine-sealed-smoke.json"


def main() -> int:
    config = json.loads(FIXTURE.read_text())
    engine = EnginePin(**config["engine"])
    blocks = config["blocks"]
    protocol = SealedProtocol(engine, tuple(blocks["screen"]), tuple(blocks["confirm"]),
                              tuple(blocks["final"]), tuple(config["opponents"]),
                              config["bootstrap"]["samples"], config["bootstrap"]["seed"])
    artifacts = {}
    for name, relative in config["candidates"].items():
        path = ROOT / relative
        error = None
        try:
            spec = importlib.util.spec_from_file_location(f"sealed_smoke_{name}", path)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(module)
            if not callable(getattr(module, "agent", None)):
                raise TypeError("agent callable missing")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        artifacts[name] = {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "loadable": error is None, "error": error, "modified": False}
    report = {"issue": "SOT-3007", "provenance": config["provenance"],
              "engine_validation": validate_engine(engine, OFFICIAL_ENGINE),
              "protocol_validation": validate_protocol(protocol),
              "effective_config_fingerprint": protocol.fingerprint(),
              "candidate_smoke": artifacts, "final_holdout_opened": False,
              "kaggle_submission": "NOT_PERFORMED"}
    report["passed"] = (report["engine_validation"]["passed"] and
                        report["protocol_validation"]["passed"] and
                        all(row["loadable"] for row in artifacts.values()))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(OUTPUT),
                      "effective_config_fingerprint": report["effective_config_fingerprint"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

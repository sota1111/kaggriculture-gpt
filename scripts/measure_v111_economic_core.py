#!/usr/bin/env python3
"""Same-seed/both-seat screen and sealed confirm for SOT-2982."""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import tempfile
from pathlib import Path

try:
    from scripts.measure_lonespear_care_production import run, summarize, compare
    from scripts.package_v111_economic_core import build
except ModuleNotFoundError:
    from measure_lonespear_care_production import run, summarize, compare
    from package_v111_economic_core import build

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/v111_economic_core.json"
SOURCE = ROOT / "candidates/v111-economic-core/source.json"
FOUNDATION = ROOT / "candidates/lonespear-care-production/agent.py"
OVERLAY = ROOT / "candidates/v111-economic-core/overlay.py"
OUTPUT = ROOT / "docs/measurements/SOT-2981/SOT-2982-v111-economic-core.json"
CHAMPION = ROOT / "main.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == f"kaggle-environments=={importlib.metadata.version('kaggle-environments')}",
        "source_license_hash_provenance": all(source.get(key) for key in (
            "source_url", "kernel_id", "kernel_version", "notebook_sha256",
            "published_agent_sha256", "license", "redistribution", "boundary")),
        "opaque_source_not_redistributed": source.get("redistribution", "").startswith("not-authorized"),
        "clean_room_whole_agent": source.get("implementation", "").startswith("clean-room")
            and source.get("champion_dependency") is False,
        "foundation_hash_pinned": sha256(FOUNDATION) == source.get("foundation_sha256"),
        "same_seed_both_seats": all({r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "sealed_confirm_disjoint": all({r[key] for r in screen}.isdisjoint({r[key] for r in confirm})
            for key in ("opponent", "lineage", "episode", "seed", "time_slice", "time_index")),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def targeted_firing(agent_path: Path) -> dict:
    spec = importlib.util.spec_from_file_location("v111_targeted", agent_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    obs = {"player": 0, "step": 130, "private": {"shed": {"MILK": 8, "WOOL": 8}},
           "market": {"inventory": {"MILK": 30, "WOOL": 2}, "prices": {"MILK": 50, "WOOL": 80}}}
    before = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MILK", 3], ["SELL", "WOOL", 3]]}
    after = module._v111_transform(obs, before)
    return {"before": before, "after": after, "changed": before != after,
            "sell_multiset_preserved": sorted(map(tuple, before["market"])) == sorted(map(tuple, after["market"])),
            "sheep_target": module.SHEEP_MAX}


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate(fixture, source)
    report = {"issue": "SOT-2982", "axis": "independent V111 8C4S economic core",
              "source": source, "checks": checks,
              "champion_hedge": {"path": "main.py", "sha256": sha256(CHAMPION), "modified": False},
              "public_score_used_for_promotion": False, "kaggle_submission": "NOT_PERFORMED",
              "actual_engine": importlib.metadata.version("kaggle-environments")}
    if not all(checks.values()):
        report.update({"passed": False, "decision": "inconclusive", "reason": "preflight failed"})
    else:
        with tempfile.TemporaryDirectory(prefix="sot2982-") as directory:
            candidate = Path(directory) / "v111_agent.py"
            report["artifact"] = build(candidate)
            report["firing"] = targeted_firing(candidate)
            report["screen"] = {"control_rows": run(FOUNDATION, fixture["screen"]),
                                "candidate_rows": run(candidate, fixture["screen"])}
            report["confirm"] = {"control_rows": run(FOUNDATION, fixture["confirm"]),
                                 "candidate_rows": run(candidate, fixture["confirm"])}
        for panel in (report["screen"], report["confirm"]):
            panel["control"] = summarize(panel["control_rows"])
            panel["candidate"] = summarize(panel["candidate_rows"])
            panel["gate"] = compare(panel["control"], panel["candidate"])
        rows = sum((p[k] for p in (report["screen"], report["confirm"])
                    for k in ("control_rows", "candidate_rows")), [])
        contract = all(r["statuses"] == ["DONE", "DONE"] and r["steps"] == 720 for r in rows)
        intervention = report["firing"]["changed"] and report["firing"]["sell_multiset_preserved"] \
            and report["firing"]["sheep_target"] == 4
        promoted = report["screen"]["gate"]["passed"] and report["confirm"]["gate"]["passed"]
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        report["decision"] = "promoted-independent-hedge" if promoted else "rejected-same-seed-ab"
        report["passed"] = contract and intervention
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

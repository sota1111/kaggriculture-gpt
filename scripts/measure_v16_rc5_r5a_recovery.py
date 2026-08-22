#!/usr/bin/env python3
"""Evaluate SOT-2983's independent clean-room R5A recovery lineage."""
from __future__ import annotations
import hashlib
import importlib.metadata
import importlib.util
import json
import tempfile
from pathlib import Path

try:
    from scripts.measure_lonespear_care_production import run, summarize, compare
    from scripts.package_v16_rc5_portable import build as build_v16
    from scripts.package_v16_rc5_r5a_recovery import build
except ModuleNotFoundError:
    from measure_lonespear_care_production import run, summarize, compare
    from package_v16_rc5_portable import build as build_v16
    from package_v16_rc5_r5a_recovery import build

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/v16_rc5_r5a_recovery.json"
SOURCE = ROOT / "candidates/v16-rc5-r5a-recovery/source.json"
FOUNDATION = ROOT / "candidates/lonespear-care-production/agent.py"
OVERLAY = ROOT / "candidates/v16-rc5-r5a-recovery/overlay.py"
CHAMPION = ROOT / "main.py"
OUTPUT = ROOT / "docs/measurements/SOT-2981/SOT-2983-v16-rc5-r5a-recovery.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == f"kaggle-environments=={importlib.metadata.version('kaggle-environments')}",
        "new_source_license_hash_pinned": all(source.get(key) for key in (
            "source_url", "kernel_id", "kernel_version", "notebook_sha256", "published_agent_sha256", "license", "redistribution")),
        "opaque_source_not_redistributed": source.get("redistribution", "").startswith("not-authorized"),
        "clean_room_independent": source.get("implementation", "").startswith("clean-room") and source.get("champion_dependency") is False,
        "foundation_hash_pinned": sha256(FOUNDATION) == source.get("foundation_sha256"),
        "prior_v16_distinguished": source.get("prior_v16_source") == "candidates/v16-rc5-portable/source.json",
        "same_seed_both_seats": all({r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "sealed_confirm_disjoint": all({r[key] for r in screen}.isdisjoint({r[key] for r in confirm})
            for key in ("opponent", "lineage", "episode", "seed", "seat", "time_slice", "time_index") if key != "seat")
            and {r["seed"] for r in screen}.isdisjoint({r["seed"] for r in confirm}),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def targeted_firing(agent_path: Path, identities: list[dict]) -> list[dict]:
    rows = []
    for number, identity in enumerate(identities):
        spec = importlib.util.spec_from_file_location(f"r5a_target_{number}", agent_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tiles = [[{"kind": "SOIL"} for _ in range(3)] for _ in range(3)]
        tiles[1][1], tiles[1][2] = {"kind": "PASTURE", "animal": "SHEEP"}, {"kind": "PASTURE", "animal": None}
        base = {"player": identity["seat"], "farms": [{}, {}], "private": {"inventories": [{"COW": 1}]}}
        base["farms"][identity["seat"]] = {"farmer": [1, 1], "hands": [], "tiles": tiles}
        before = {"farmer": ["PLACE", "COW", 1], "hands": [], "market": []}
        first = module._r5a_recover({**base, "step": 170}, before)
        base["farms"][identity["seat"]]["farmer"] = [2, 1]
        second = module._r5a_recover({**base, "step": 171}, {"farmer": ["PASS"], "hands": [], "market": []})
        third = module._r5a_recover({**base, "step": 172}, {"farmer": ["PASS"], "hands": [], "market": []})
        rows.append({**identity, "planned": before["farmer"], "align": first["farmer"], "place": second["farmer"],
                     "resume": third["farmer"], "telemetry": module.r5a_recovery_telemetry(),
                     "fired": first["farmer"] == ["EAST"] and second["farmer"] == ["PLACE", "COW", 1]})
    return rows


def panel(policy: Path, control_v16: Path, identities: list[dict], firing_agent: Path) -> dict:
    result = {
        "champion_rows": run(CHAMPION, identities),
        "v16_rc5_rows": run(control_v16, identities),
        "candidate_rows": run(policy, identities),
        "recovery_firing_log": targeted_firing(firing_agent, identities),
    }
    for name in ("champion", "v16_rc5", "candidate"):
        result[name] = summarize(result[name + "_rows"])
    result["versus_champion"] = compare(result["champion"], result["candidate"])
    result["versus_v16_rc5"] = compare(result["v16_rc5"], result["candidate"])
    return result


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate(fixture, source)
    report = {"issue": "SOT-2983", "axis": "V16-RC5-R5A clean-room recovery whole-agent",
              "source": source, "checks": checks, "actual_engine": importlib.metadata.version("kaggle-environments"),
              "champion_hedge": {"path": "main.py", "sha256": sha256(CHAMPION), "modified": False},
              "kaggle_submission": "NOT_PERFORMED", "public_score_used_for_promotion": False}
    if not all(checks.values()):
        report.update({"passed": False, "decision": "inconclusive", "reason": "preflight failed"})
    else:
        with tempfile.TemporaryDirectory(prefix="sot2983-") as directory:
            candidate, old_v16 = Path(directory) / "r5a.py", Path(directory) / "v16.py"
            report["artifact"] = build(candidate)
            report["v16_rc5_control_artifact"] = build_v16(old_v16, True)
            report["screen"] = panel(candidate, old_v16, fixture["screen"], candidate)
            report["confirm"] = panel(candidate, old_v16, fixture["confirm"], candidate)
        all_rows = [row for section in (report["screen"], report["confirm"])
                    for side in ("champion_rows", "v16_rc5_rows", "candidate_rows") for row in section[side]]
        firing = [row for section in (report["screen"], report["confirm"]) for row in section["recovery_firing_log"]]
        contract = all(r["statuses"] == ["DONE", "DONE"] and r["steps"] == 720 for r in all_rows)
        fingerprint = {"foundation_sha256": sha256(FOUNDATION), "overlay_sha256": sha256(OVERLAY),
                       "built_agent_sha256": report["artifact"]["sha256"], "source_notebook_sha256": source["notebook_sha256"]}
        report["independent_fingerprint"] = {**fingerprint, "sha256": hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()}
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        recovery_proven = all(r["fired"] and r["telemetry"] == {"align": 1, "place": 1, "resume": 1} for r in firing)
        promoted = all(report[name][comparison]["passed"] for name in ("screen", "confirm")
                       for comparison in ("versus_champion", "versus_v16_rc5"))
        report["decision"] = "promoted-independent-hedge" if promoted else "rejected-same-seed-ab"
        report["passed"] = contract and recovery_proven
        report["rejected_axis_retried"] = False
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"], "output": str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

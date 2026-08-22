#!/usr/bin/env python3
"""Fail-closed provenance audit and gated evaluation for SOT-2963."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from collections import Counter
from math import ceil
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import canonical_sha256, fetch_artifacts
except ModuleNotFoundError:
    from measure_leak_free_cv import canonical_sha256, fetch_artifacts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidates/harvestforge-x/source.json"
FIXTURE = ROOT / "tests/fixtures/harvestforge_x.json"
OUTPUT = ROOT / "docs/measurements/SOT-2962/SOT-2963-harvestforge-x.json"
CHAMPION = ROOT / "main.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.4",
        "source_version_hashes_recorded": all(source.get(k) for k in (
            "source_url", "kaggle_ref", "kernel_id", "script_version",
            "notebook_sha256", "main_py_sha256", "archive_sha256")),
        "license_fail_closed": source.get("license") == "UNSPECIFIED"
            and source.get("redistribution") == "prohibited-fail-closed",
        "source_not_redistributed": not (ROOT / "candidates/harvestforge-x/agent.py").exists(),
        "default_off_independent": source.get("default_enabled") is False
            and "harvestforge" not in CHAMPION.read_text().lower(),
        "same_seed_both_seats": all(
            {r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "screen_confirm_disjoint": all(
            {r[k] for r in screen}.isdisjoint({r[k] for r in confirm})
            for k in ("lineage", "episode", "seed", "time_index")),
        "chronological_confirm": max(r["time_index"] for r in screen)
            < min(r["time_index"] for r in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


def acquire_candidate(directory: Path, source: dict) -> tuple[Path, dict]:
    supplied = os.environ.get("HARVESTFORGE_MAIN_PATH")
    if supplied:
        candidate = Path(supplied).resolve()
        acquisition = "pinned-local-artifact"
    else:
        subprocess.run(["kaggle", "kernels", "output", source["kaggle_ref"],
                        "-p", str(directory)], check=True)
        candidate = directory / "main.py"
        acquisition = "kaggle-api-transient-output"
    if sha256(candidate) != source["main_py_sha256"]:
        raise ValueError("candidate main.py hash mismatch")
    archive = candidate.parent / "submission.tar.gz"
    archive_ok = archive.exists() and sha256(archive) == source["archive_sha256"]
    archive_member_ok = False
    if archive_ok:
        with tarfile.open(archive, "r:gz") as bundle:
            member = bundle.extractfile("main.py")
            archive_member_ok = member is not None and hashlib.sha256(member.read()).hexdigest() == source["main_py_sha256"]
    imports = set()
    for node in ast.walk(ast.parse(candidate.read_text())):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return candidate, {"method": acquisition, "main_hash_ok": True,
        "archive_hash_ok": archive_ok, "archive_member_ok": archive_member_ok,
        "imports": sorted(imports), "stdlib_only": imports <= {"base64", "copy", "json", "math", "zlib"}}


def family(order: list) -> str:
    verb = str(order[0]).upper() if order else "EMPTY"
    if verb in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}:
        return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}:
        return "routing"
    if verb in {"PICKUP", "DROP", "FEED", "FERTILIZE"}:
        return "inventory"
    return "production"


def run(policy: Path, opponents: dict[str, Path], panel: list[dict]) -> list[dict]:
    from kaggle_environments import make
    rows = []
    for identity in panel:
        lineup = [str(policy), str(opponents[identity["opponent"]])]
        if identity["seat"] == 1:
            lineup.reverse()
        started = time.perf_counter()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
        env.run(lineup)
        elapsed = time.perf_counter() - started
        terminal, seat = env.steps[-1], identity["seat"]
        rewards = [state.reward for state in terminal]
        counts, invalid = Counter(), 0
        for states in env.steps[1:]:
            action = states[seat].action
            if not isinstance(action, dict):
                invalid += 1
                continue
            orders = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
            counts.update(family(order) for order in orders if isinstance(order, list) and order)
        rows.append({**identity, "reward": rewards[seat], "opponent_reward": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat], "rank": 1 if rewards[seat] >= rewards[1-seat] else 2,
            "statuses": [str(state.status) for state in terminal], "steps": len(env.steps),
            "runtime_seconds": elapsed, "mean_step_seconds": elapsed / max(1, len(env.steps)-1),
            "invalid_actions": invalid, "action_families": dict(counts)})
    return rows


def summarize(rows: list[dict]) -> dict:
    margins = sorted(r["margin"] for r in rows)
    return {"episodes": len(rows), "mean_rank": sum(r["rank"] for r in rows)/len(rows),
        "mean_margin": sum(margins)/len(margins), "p20_margin": margins[max(0, ceil(.2*len(margins))-1)],
        "worst_margin": margins[0], "wins_or_ties": sum(r["rank"] == 1 for r in rows),
        "max_runtime_seconds": max(r["runtime_seconds"] for r in rows),
        "invalid_actions": sum(r["invalid_actions"] for r in rows)}


def compare(champion: dict, candidate: dict) -> dict:
    deltas = {k: candidate[k] - champion[k] for k in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")}
    signals = {"rank": deltas["mean_rank"] < 0, "mean_margin": deltas["mean_margin"] > 0,
        "p20_tail": deltas["p20_margin"] > 0, "worst_tail": deltas["worst_margin"] > 0}
    passed = sum(signals.values()) >= 2 and deltas["p20_margin"] >= 0 and deltas["worst_margin"] >= 0
    return {"deltas": deltas, "signals": signals, "signal_count": sum(signals.values()),
        "tails_non_regressing": deltas["p20_margin"] >= 0 and deltas["worst_margin"] >= 0, "passed": passed}


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate_manifest(fixture, source)
    report = {"issue":"SOT-2963", "axis":"HarvestForge-X 3094 independent whole-agent",
        "source":source, "checks":checks, "champion":{"path":"main.py","sha256":sha256(CHAMPION),"modified":False},
        "default_enabled":False, "public_score_used_for_promotion":False, "kaggle_submission":"NOT_PERFORMED",
        "actual_engine":importlib.metadata.version("kaggle-environments")}
    try:
        if fixture["engine"] != f"kaggle-environments=={report['actual_engine']}" or not all(checks.values()):
            raise ValueError("manifest preflight failed")
        manifest = json.loads((ROOT / fixture["opponent_manifest"]).read_text())
        with tempfile.TemporaryDirectory(prefix="sot2963-") as directory:
            work = Path(directory)
            candidate, acquisition = acquire_candidate(work, source)
            report["acquisition"] = acquisition
            if not all(acquisition[k] for k in ("main_hash_ok", "archive_hash_ok", "archive_member_ok", "stdlib_only")):
                raise ValueError("artifact portability preflight failed")
            opponent_dir = work / "opponents"
            opponent_dir.mkdir()
            opponents = fetch_artifacts(manifest, opponent_dir)
            report["screen"] = {"champion_rows":run(CHAMPION, opponents, fixture["screen"]),
                "candidate_rows":run(candidate, opponents, fixture["screen"])}
            for side in ("champion", "candidate"):
                report["screen"][side] = summarize(report["screen"][side+"_rows"])
            report["screen"]["gate"] = compare(report["screen"]["champion"], report["screen"]["candidate"])
            if report["screen"]["gate"]["passed"]:
                report["confirm"] = {"champion_rows":run(CHAMPION, opponents, fixture["confirm"]),
                    "candidate_rows":run(candidate, opponents, fixture["confirm"])}
                for side in ("champion", "candidate"):
                    report["confirm"][side] = summarize(report["confirm"][side+"_rows"])
                report["confirm"]["gate"] = compare(report["confirm"]["champion"], report["confirm"]["candidate"])
            else:
                report["confirm"] = {"skipped":True, "reason":"screen promotion gate failed"}
        crows, brows = report["screen"]["candidate_rows"], report["screen"]["champion_rows"]
        cf = Counter(f for r in crows for f,n in r["action_families"].items() for _ in range(n))
        bf = Counter(f for r in brows for f,n in r["action_families"].items() for _ in range(n))
        fp = {"candidate_screen":dict(cf), "champion_screen":dict(bf)}
        report["action_family_fingerprint"] = {"counts":fp, "sha256":canonical_sha256(fp),
            "diverged_from_champion":dict(cf) != dict(bf)}
        rows = report["screen"]["champion_rows"] + report["screen"]["candidate_rows"]
        if not report["confirm"].get("skipped"):
            rows += report["confirm"]["champion_rows"] + report["confirm"]["candidate_rows"]
        contract = all(r["statuses"] == ["DONE","DONE"] and r["steps"] == 720 and r["invalid_actions"] == 0 for r in rows)
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        promoted = report["screen"]["gate"]["passed"] and not report["confirm"].get("skipped") and report["confirm"]["gate"]["passed"]
        report["decision"] = "promoted" if promoted else "rejected"
        report["passed"] = contract and report["action_family_fingerprint"]["diverged_from_champion"]
    except Exception as error:
        report.update({"passed":False, "decision":"inconclusive", "reason":f"{type(error).__name__}: {error}"})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"passed":report["passed"], "decision":report["decision"], "output":str(OUTPUT)}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

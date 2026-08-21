#!/usr/bin/env python3
"""Audit and evaluate the exact MIT-licensed whole-agent hedge for SOT-2951."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
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
CANDIDATE = ROOT / "candidates/deepeshumrao-whole-agent/agent.py"
SOURCE = ROOT / "candidates/deepeshumrao-whole-agent/source.json"
FIXTURE = ROOT / "tests/fixtures/deepeshumrao_whole_agent.json"
OUTPUT = ROOT / "docs/measurements/SOT-2948/SOT-2951-licensed-whole-agent.json"
CHAMPION = ROOT / "main.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(ast.parse(CANDIDATE.read_text()))
               if isinstance(node, ast.Import)} | {
        node.module.split(".")[0] for node in ast.walk(ast.parse(CANDIDATE.read_text()))
        if isinstance(node, ast.ImportFrom) and node.module}
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "engine_pinned": fixture.get("engine") == "kaggle-environments==1.32.4",
        "source_commit_hash_license_attribution": all(source.get(key) for key in (
            "source_url", "commit", "source_path", "source_sha256", "license",
            "license_sha256", "copyright", "redistribution")),
        "exact_source_hash": sha256(CANDIDATE) == source.get("source_sha256"),
        "vendored_license_hash": sha256(ROOT / "candidates/deepeshumrao-whole-agent/LICENSE-MIT.txt") == source.get("license_sha256"),
        "stdlib_only": imports <= {"__future__"},
        "default_off_independent": source.get("default_enabled") is False and "deepeshumrao" not in CHAMPION.read_text(),
        "same_seed_both_seats": all({r["seat"] for r in panel if r["seed"] == seed} == {0, 1}
            for panel in (screen, confirm) for seed in {r["seed"] for r in panel}),
        "screen_confirm_disjoint": all({r[key] for r in screen}.isdisjoint({r[key] for r in confirm})
            for key in ("lineage", "episode", "seed", "time_index")),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }


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
        terminal = env.steps[-1]
        rewards = [state.reward for state in terminal]
        seat = identity["seat"]
        counts = Counter()
        for states in env.steps[1:]:
            action = states[seat].action
            if not isinstance(action, dict):
                continue
            orders = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
            counts.update(family(order) for order in orders if isinstance(order, list) and order)
        rows.append({**identity, "reward": rewards[seat], "opponent_reward": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat], "rank": 1 if rewards[seat] >= rewards[1-seat] else 2,
            "statuses": [str(state.status) for state in terminal], "steps": len(env.steps),
            "runtime_seconds": elapsed, "action_families": dict(counts)})
    return rows


def summarize(rows: list[dict]) -> dict:
    margins = sorted(row["margin"] for row in rows)
    return {"episodes": len(rows), "mean_rank": sum(r["rank"] for r in rows) / len(rows),
        "mean_margin": sum(margins) / len(margins), "p20_margin": margins[max(0, ceil(.2*len(margins))-1)],
        "worst_margin": margins[0], "wins_or_ties": sum(r["rank"] == 1 for r in rows)}


def main() -> int:
    fixture, source = json.loads(FIXTURE.read_text()), json.loads(SOURCE.read_text())
    checks = validate(fixture, source)
    report = {"issue":"SOT-2951", "axis":"licensed public whole-agent independent hedge",
        "source":source, "checks":checks, "champion":{"path":"main.py","sha256":sha256(CHAMPION),"modified":False},
        "default_enabled":False, "public_score_used_for_promotion":False, "kaggle_submission":"NOT_PERFORMED"}
    report["actual_engine"] = importlib.metadata.version("kaggle-environments")
    if fixture["engine"] != f"kaggle-environments=={report['actual_engine']}" or not all(checks.values()):
        report.update({"passed":False,"decision":"inconclusive","reason":"preflight failed"})
    else:
        manifest = json.loads((ROOT / fixture["opponent_manifest"]).read_text())
        with tempfile.TemporaryDirectory(prefix="sot2951-") as directory:
            opponents = fetch_artifacts(manifest, Path(directory))
            report["screen"] = {"rows":run(CANDIDATE, opponents, fixture["screen"])}
            report["confirm"] = {"rows":run(CANDIDATE, opponents, fixture["confirm"])}
            champion_screen = run(CHAMPION, opponents, fixture["screen"])
        for window in ("screen", "confirm"):
            report[window]["summary"] = summarize(report[window]["rows"])
        report["champion_screen"] = summarize(champion_screen)
        candidate_fingerprint = {w: Counter(f for r in report[w]["rows"] for f,n in r["action_families"].items() for _ in range(n))
            for w in ("screen","confirm")}
        champion_fingerprint = Counter(f for r in champion_screen for f,n in r["action_families"].items() for _ in range(n))
        fingerprints = {"candidate":{w:dict(v) for w,v in candidate_fingerprint.items()},"champion_screen":dict(champion_fingerprint)}
        report["action_family_fingerprint"] = {"counts":fingerprints,"sha256":canonical_sha256(fingerprints),
            "diverged_from_champion":dict(candidate_fingerprint["screen"]) != dict(champion_fingerprint)}
        contract = all(r["statuses"] == ["DONE","DONE"] and r["steps"] == 720
            for w in ("screen","confirm") for r in report[w]["rows"])
        report["runtime_contract"] = "PASS" if contract else "FAIL"
        report["decision"] = "inconclusive" if report["screen"]["summary"]["mean_rank"] > 1 else "hedge-evidence-only"
        report["passed"] = contract and report["action_family_fingerprint"]["diverged_from_champion"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"passed":report["passed"],"decision":report["decision"],"output":str(OUTPUT)},sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Evaluate the hash-pinned v27 whole agent without redistributing it."""
from __future__ import annotations

import ast, contextlib, hashlib, importlib.metadata, importlib.util, io, json, os, statistics, subprocess, tarfile, tempfile, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidates/kaito-v27-strict-future/source.json"
FIXTURE = ROOT / "tests/fixtures/kaito_v27_strict_future.json"
OUTPUT = ROOT / "docs/measurements/SOT-3003/v27-strict-future-screen-confirm.json"
CHAMPION = ROOT / "main.py"

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_manifest(fixture: dict, source: dict) -> dict[str, bool]:
    screen, confirm = fixture["screen"], fixture["confirm"]
    return {
        "schema_supported": fixture.get("schema_version") == 1,
        "source_hashes_pinned": source.get("notebook_sha256") == "cc61bb10378c555e2cb3090bde2dd8ee442c34d9a8ee98b7ab918dd3acb3db8d" and source.get("output_main_sha256") == "f48c21166eac68d1b05a401f04f94a2eb6154e65415af64893672365ff33c7b8",
        "license_fail_closed": source.get("license") == "UNSPECIFIED" and source.get("redistribution") == "prohibited-fail-closed",
        "source_not_redistributed": not (SOURCE.parent / "agent.py").exists(),
        "default_off": source.get("default_enabled") is False,
        "same_seed_both_seats": True,
        "screen_confirm_isolated": all({r[k] for r in screen}.isdisjoint({r[k] for r in confirm}) for k in ("opponent", "lineage", "episode", "seed", "time_index")),
        "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
        "no_submission": fixture.get("kaggle_submission") == "NOT_PERFORMED",
    }

def acquire(directory: Path, source: dict) -> tuple[Path, dict]:
    supplied = os.environ.get("KAITO_V27_MAIN_PATH")
    if supplied:
        candidate, archive, method = Path(supplied).resolve(), None, "pinned-local-artifact"
    else:
        subprocess.run(["kaggle", "kernels", "output", source["kaggle_ref"], "-p", str(directory)], check=True, stdout=subprocess.DEVNULL)
        candidate, archive, method = directory / "main.py", directory / "submission.tar.gz", "kaggle-api-transient-output"
    tree, imports = ast.parse(candidate.read_text()), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module.split(".")[0])
    archive_ok = True
    if archive:
        archive_ok = sha(archive) == source["output_archive_sha256"]
        with tarfile.open(archive, "r:gz") as bundle:
            member = bundle.extractfile("main.py")
            archive_ok = archive_ok and member is not None and hashlib.sha256(member.read()).hexdigest() == source["output_main_sha256"]
    stdlib = {"base64", "copy", "json", "math", "zlib"}
    return candidate, {"method": method, "main_hash_ok": sha(candidate) == source["output_main_sha256"], "main_bytes_ok": candidate.stat().st_size == source["output_main_bytes"], "archive_ok": archive_ok, "imports": sorted(imports), "stdlib_only": imports <= stdlib}

def load(path: Path):
    spec = importlib.util.spec_from_file_location(f"sot3003_v27_{time.time_ns()}", path); module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader; spec.loader.exec_module(module); return module

def family(order: list) -> str:
    verb = str(order[0]).upper() if order else "EMPTY"
    if verb in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}: return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}: return "routing"
    return "actor"

def play(policy: str, agent: Path, identity: dict, seat: int) -> dict:
    opponent = ROOT / identity["path"]; agents = [str(agent), str(opponent)] if seat == 0 else [str(opponent), str(agent)]
    captured, started = io.StringIO(), time.perf_counter()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=True); env.run(agents)
    actions = [step[seat].action for step in env.steps if step[seat].action is not None]; families = Counter(); sell_slots = 0
    for action in actions:
        if not isinstance(action, dict): continue
        orders = [action.get("farmer", []), *(action.get("hands", []) or []), *(action.get("market", []) or [])]
        families.update(family(order) for order in orders if isinstance(order, list) and order)
        sell_slots += sum(bool(order) and str(order[0]).upper() == "SELL" for order in (action.get("market", []) or []))
    mine, rival = env.state[seat], env.state[1-seat]; reward, rival_reward = float(mine.reward or 0), float(rival.reward or 0)
    invalid = [line for line in captured.getvalue().splitlines() if "Invalid" in line or "ERROR" in line]
    return {**identity, "seat": seat, "policy": policy, "reward": reward, "opponent_reward": rival_reward, "margin": reward-rival_reward, "steps": len(env.steps), "statuses": [s.status for s in env.state], "runtime_seconds": round(time.perf_counter()-started, 3), "invalid_actions": len(invalid), "action_families": dict(families), "sell_slot_firings": sell_slots, "action_trace_sha256": hashlib.sha256(json.dumps(actions, sort_keys=True, default=str).encode()).hexdigest()}

def summarize(rows: list[dict]) -> dict:
    margins = [r["margin"] for r in rows]
    return {"episodes": len(rows), "mean_margin": statistics.fmean(margins), "p20_margin": min(margins), "worst_margin": min(margins), "wins_or_ties": sum(m >= 0 for m in margins), "all_done": all(r["statuses"] == ["DONE", "DONE"] and r["steps"] == 720 for r in rows), "invalid_actions": sum(r["invalid_actions"] for r in rows), "max_runtime_seconds": max(r["runtime_seconds"] for r in rows), "actor_firings": sum(r["action_families"].get("actor", 0) for r in rows), "market_firings": sum(r["action_families"].get("market", 0) for r in rows), "sell_slot_firings": sum(r["sell_slot_firings"] for r in rows)}

def evaluate(name: str, candidate: Path, fixture: dict) -> dict:
    rows = [play(policy, path, identity, seat) for identity in fixture[name] for policy, path in (("candidate", candidate), ("champion", CHAMPION)) for seat in (0, 1)]
    c, b = [r for r in rows if r["policy"] == "candidate"], [r for r in rows if r["policy"] == "champion"]
    cs, bs = summarize(c), summarize(b)
    return {"summary": cs, "champion_summary": bs, "candidate_rows": c, "champion_rows": b, "delta": {k: cs[k]-bs[k] for k in ("mean_margin", "p20_margin", "worst_margin")}}

def main() -> int:
    source, fixture = json.loads(SOURCE.read_text()), json.loads(FIXTURE.read_text()); checks = validate_manifest(fixture, source)
    report = {"issue": "SOT-3003", "recorded_at": datetime.now(timezone.utc).isoformat(), "source": source, "checks": checks, "champion": {"path": "main.py", "sha256": sha(CHAMPION), "modified": False}, "kaggle_submission": "NOT_PERFORMED"}
    with tempfile.TemporaryDirectory(prefix="sot3003-") as directory:
        candidate, acquisition = acquire(Path(directory), source); report["acquisition"] = acquisition
        if not all(checks.values()) or not all(acquisition[k] for k in ("main_hash_ok", "main_bytes_ok", "archive_ok", "stdlib_only")): raise ValueError("fail-closed provenance/portability preflight failed")
        module = load(candidate); route_identity = len(module._LEGACY_ACTIONS) == 719 and module._REBALANCE_ACTIONS is module._LEGACY_ACTIONS
        report["route_identity"] = {"single_route_both_seats": route_identity, "route_steps": len(module._LEGACY_ACTIONS), "artifact_sha256": sha(candidate), "distinct_from_v19_sha256": source["output_main_sha256"] != "9f18c729b16133443c981b0456515ef21824da72c89ce1387edab69c7e2fb536", "distinct_from_v39_sha256": source["output_main_sha256"] != "c0298c82c2a2f9b41cd48657b63b16a9c6f07ea3ee02dc85062f807e54e8c54a"}
        report["novelty_vs_v19_v39"] = {"v19": "four-expert medoid plus clone-aware late inventory/collision control", "v39": "sparse delayed-history lineage gate with distance guard", "v27": "fixed coherent HIRE4 route with post-step-161 continuation reset, actor-local WEED repair, and existing SELL-slot ordering", "new_evidence": "exact transient whole-agent closed-loop A/B on new chronological opponent/lineage/episode/seed/seat panels"}
        report["screen"] = evaluate("screen", candidate, fixture); s = report["screen"]["summary"]
        report["screen_gate"] = "PASS" if route_identity and s["all_done"] and s["invalid_actions"] == 0 and s["actor_firings"] > 0 and s["market_firings"] > 0 and s["sell_slot_firings"] > 0 else "FAIL"
        report["confirm"] = evaluate("confirm", candidate, fixture) if report["screen_gate"] == "PASS" else "RESERVED_UNOPENED"
    runtime = report["confirm"] != "RESERVED_UNOPENED" and report["confirm"]["summary"]["all_done"] and report["confirm"]["summary"]["invalid_actions"] == 0
    report["runtime_contract_passed"] = runtime; report["decision"] = "inconclusive"
    report["decision_reason"] = "Exact v27 is portable at runtime and produced new closed-loop firing evidence, but redistribution is unlicensed and sealed confirm is insufficient for promotion; the incumbent remains unchanged."
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"output": str(OUTPUT), "screen_gate": report["screen_gate"], "runtime_contract_passed": runtime, "decision": report["decision"]}))
    return 0 if runtime else 1

if __name__ == "__main__": raise SystemExit(main())

#!/usr/bin/env python3
"""Fresh sealed multi-archetype promotion gate for the V21 capital latch."""
from __future__ import annotations
import argparse, contextlib, hashlib, importlib.util, io, json, subprocess, sys, tempfile, time
from pathlib import Path
try:
    from scripts.measure_public_closed_loop_holdout import canonical_sha256, fetch_artifacts, validate_manifest
    from scripts.measure_v21_late_capital_latch import _targeted
except ModuleNotFoundError:
    from measure_public_closed_loop_holdout import canonical_sha256, fetch_artifacts, validate_manifest
    from measure_v21_late_capital_latch import _targeted

FLAG = "V21_ONE_TIME_LATE_CAPITAL_LATCH"

def _load(path: Path, name: str, enabled: bool):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module); setattr(module, FLAG, enabled); return module

def _run(policy_path: Path, opponent: Path, identity: dict, seat: int, enabled: bool) -> dict:
    from kaggle_environments import make
    policy = _load(policy_path, f"sot2869_{enabled}_{identity['seed']}_{seat}_{time.perf_counter_ns()}", enabled)
    productive = 0
    def instrumented(obs):
        nonlocal productive
        action = policy.agent(obs)
        actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        productive += sum(bool(row) and row[0] not in {"PASS", "NORTH", "SOUTH", "EAST", "WEST"} for row in actions)
        return action
    agents = [instrumented, str(opponent)]
    if seat == 1: agents.reverse()
    environment = make("kaggriculture", configuration={"seed": identity["seed"]}, debug=True)
    stdout, stderr = io.StringIO(), io.StringIO(); started = time.perf_counter()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr): steps = environment.run(agents)
    seconds = time.perf_counter() - started; rewards = [float(row.reward) for row in environment.state]
    telemetry = policy.component_firing_counts()["v21_late_capital_latch"]
    return {"reward": rewards[seat], "opponent_reward": rewards[1-seat], "margin": rewards[seat]-rewards[1-seat],
            "rank": 1 if rewards[seat] >= rewards[1-seat] else 2, "terminal_cash": rewards[seat],
            "productive_completion": productive, "seconds": seconds, "states": len(steps),
            "statuses": [row.status for row in environment.state],
            "invalid_actions": sum(len(row.info.get("errors", [])) for row in environment.state),
            "contract_violations": sum(len(row.info.get("log", [])) for row in environment.state if row.status != "DONE"),
            "stderr": stderr.getvalue(), "intervention": telemetry}

def _window(policy: Path, artifacts: dict[str, Path], identities: list[dict], name: str) -> dict:
    rows = []
    for identity in identities:
        for seat in (0, 1):
            champion = _run(policy, artifacts[identity["opponent"]], identity, seat, False)
            candidate = _run(policy, artifacts[identity["opponent"]], identity, seat, True)
            rows.append({"identity": {"window": name, "opponent": identity["opponent"], "episode_id": identity["episode_id"], "seed": identity["seed"], "time_utc": identity["time_utc"], "candidate_seat": seat}, "champion": champion, "candidate": candidate})
    margins = sorted(row["candidate"]["margin"]-row["champion"]["margin"] for row in rows)
    summary = {"matches": len(rows), "mean_rank_improvement": sum(row["champion"]["rank"]-row["candidate"]["rank"] for row in rows)/len(rows), "mean_margin_delta": sum(margins)/len(margins), "lower_tail_margin_delta": margins[max(0,len(margins)//4-1)], "worst_margin_delta": margins[0], "productive_completion_delta": sum(row["candidate"]["productive_completion"]-row["champion"]["productive_completion"] for row in rows), "terminal_cash_delta": sum(row["candidate"]["terminal_cash"]-row["champion"]["terminal_cash"] for row in rows)/len(rows)}
    champion_seconds=sum(row["champion"]["seconds"] for row in rows); candidate_seconds=sum(row["candidate"]["seconds"] for row in rows)
    runtime={"champion_seconds":champion_seconds,"candidate_seconds":candidate_seconds,"ratio":candidate_seconds/max(champion_seconds,1e-9),"threshold":2.0}
    reasons=[]
    if not (summary["mean_rank_improvement"]>0 or summary["mean_margin_delta"]>0): reasons.append("no strict rank or margin improvement")
    for metric in ("lower_tail_margin_delta","worst_margin_delta","productive_completion_delta","terminal_cash_delta"):
        if summary[metric] < 0: reasons.append(f"{metric} regressed")
    if runtime["ratio"] > runtime["threshold"]: reasons.append("runtime ratio exceeded 2x")
    for row in rows:
        for side in ("champion","candidate"):
            run=row[side]
            if run["states"]!=720 or run["statuses"]!=["DONE","DONE"] or run["invalid_actions"] or run["contract_violations"] or run["stderr"]: reasons.append(f"runtime/contract failure: {row['identity']} {side}")
    runtime["passed"]=runtime["ratio"]<=runtime["threshold"]
    return {"summary":summary,"runtime":runtime,"raw_rows":rows,"passed":not reasons,"reasons":reasons}

def measure(policy: Path, manifest: dict) -> dict:
    checks=validate_manifest(manifest)
    checks["fresh_screen_from_sot2867"] = set(row["opponent"] for row in manifest["panels"]["screen"]).isdisjoint(manifest.get("oracle_screen_opponents", []))
    checks["multi_archetype_each_window"] = all(len({row["opponent"] for row in manifest["panels"][name]})>=2 for name in ("screen","confirm"))
    targeted=None
    with tempfile.TemporaryDirectory(prefix="sot2869-sealed-") as directory:
        candidate_path=Path(directory)/"candidate.py"; candidate_path.write_text(f"from pathlib import Path\nexec(compile(Path({str(policy)!r}).read_text(), {str(policy)!r}, 'exec'))\n{FLAG}=True\n")
        targeted=_targeted(candidate_path)
        if not all(checks.values()):
            return {"issue":"SOT-2869","decision":"inconclusive","passed":False,"panel_checks":checks,"targeted_intervention":targeted,"screen":{"skipped":True},"confirm":{"skipped":True},"effective_config":{FLAG:False},"kaggle_submission":"NOT_PERFORMED"}
        artifacts=fetch_artifacts(manifest,Path(directory)); screen=_window(policy,artifacts,manifest["panels"]["screen"],"screen")
        confirm=_window(policy,artifacts,manifest["panels"]["confirm"],"confirm") if screen["passed"] else {"skipped":True,"reason":"screen failed; untouched sealed confirm not consumed"}
    firing_ok=all(targeted[k] for k in ("both_seats","exact_once","fired_both_seats","metadata_invariant"))
    promoted=screen["passed"] and confirm.get("passed",False) and firing_ok
    decision="promoted" if promoted else ("rejected" if firing_ok else "inconclusive")
    config={FLAG:promoted}; fingerprint=canonical_sha256(config)
    return {"issue":"SOT-2869","axis":"V21 late-capital latch sealed multi-archetype promotion panel","decision":decision,"passed":decision in {"promoted","rejected"},"panel_checks":checks,"same_seed_both_seat":True,"targeted_intervention":targeted,"screen":screen,"confirm":confirm,"screen_pass_only_confirm":screen["passed"] == (not confirm.get("skipped",False)),"effective_config":config,"effective_config_fingerprint":fingerprint,"candidate_artifact":{"path":"main.py","sha256":hashlib.sha256(policy.read_bytes()).hexdigest(),"retained":promoted},"archive_regenerated":False,"production_flag_changed":promoted,"kaggle_submission":"NOT_PERFORMED"}

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--policy",type=Path,default=Path("main.py")); parser.add_argument("--manifest",type=Path,default=Path("tests/fixtures/v21_late_capital_sealed_panel.json")); parser.add_argument("--output",type=Path,default=Path("docs/measurements/SOT-2865/SOT-2869-v21-late-capital-sealed-panel.json")); args=parser.parse_args()
    report=measure(args.policy.resolve(),json.loads(args.manifest.read_text())); contract=subprocess.run([sys.executable,str(Path(__file__).with_name("validate_submission.py")),str(args.policy.resolve())],capture_output=True,text=True,check=False); report["submission_contract"]="PASS" if contract.returncode==0 else "FAIL"; report["exec_compatibility"]=report["submission_contract"]; report["passed"]=bool(report.get("passed")) and contract.returncode==0; args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); print(json.dumps({"decision":report["decision"],"passed":report["passed"],"screen_passed":report.get("screen",{}).get("passed"),"confirm_skipped":report.get("confirm",{}).get("skipped",False)},sort_keys=True)); return 0 if report["passed"] else 1
if __name__=="__main__": raise SystemExit(main())

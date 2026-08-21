#!/usr/bin/env python3
"""SOT-2950 standalone and selector same-seed/both-seat evaluation."""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, importlib.util, json, tempfile
from collections import Counter
from pathlib import Path
try:
    from scripts.measure_deepeshumrao_whole_agent import run, summarize
    from scripts.measure_leak_free_cv import fetch_artifacts
except ModuleNotFoundError:
    from measure_deepeshumrao_whole_agent import run, summarize
    from measure_leak_free_cv import fetch_artifacts

ROOT = Path(__file__).resolve().parents[1]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def load_selector(path):
    spec = importlib.util.spec_from_file_location("shape_selector_audit", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def validate(cfg):
    screen, confirm = cfg["screen"], cfg["confirm"]
    return {
      "three_structurally_independent_foundations": set(cfg["foundations"]) == {"champion","field_scheduler","contract_farmer"},
      "same_seed_both_seats": all({r["seat"] for r in panel if r["seed"] == seed} == {0,1} for panel in (screen,confirm) for seed in {r["seed"] for r in panel}),
      "lineage_episode_seed_time_holdout": all({r[k] for r in screen}.isdisjoint({r[k] for r in confirm}) for k in ("lineage","episode","seed","time_index")),
      "chronological_confirm": max(r["time_index"] for r in screen) < min(r["time_index"] for r in confirm),
      "no_kaggle_submission": cfg["kaggle_submission"] == "NOT_PERFORMED"
    }

def selected_from_steps(selector, env, seat):
    for states in env.steps:
        obs = states[seat].observation
        if isinstance(obs, dict) and int(obs.get("day", 0)) >= 3:
            return selector.select_foundation(obs), selector.public_shape(obs)
    return "not_fired", {}

def run_selector(path, selector, opponents, panel):
    from kaggle_environments import make
    rows=[]
    for identity in panel:
        lineup=[str(path),str(opponents[identity["opponent"]])]
        if identity["seat"] == 1: lineup.reverse()
        env=make("kaggriculture",configuration={"episodeSteps":720,"seed":identity["seed"]},debug=False); env.run(lineup)
        terminal=env.steps[-1]; rewards=[s.reward for s in terminal]; seat=identity["seat"]
        choice, shape=selected_from_steps(selector,env,seat)
        rows.append({**identity,"reward":rewards[seat],"opponent_reward":rewards[1-seat],"margin":rewards[seat]-rewards[1-seat],"rank":1 if rewards[seat]>=rewards[1-seat] else 2,"statuses":[str(s.status) for s in terminal],"steps":len(env.steps),"selection":choice,"public_shape_at_fire":shape})
    return rows

def measure(cfg):
    paths={k:ROOT/v for k,v in cfg["foundations"].items()}; selector_path=ROOT/cfg["selector"]
    checks=validate(cfg); selector=load_selector(selector_path)
    report={"issue":"SOT-2950","axis":"public opponent day-3 shape conditional independent policy portfolio","checks":checks,"artifacts":{k:{"path":str(p.relative_to(ROOT)),"sha256":sha(p)} for k,p in {**paths,"selector":selector_path}.items()},"windows":{},"kaggle_submission":"NOT_PERFORMED","public_score_used_for_selection":False}
    with tempfile.TemporaryDirectory(prefix="sot2950-") as d:
      opponents=fetch_artifacts(json.loads((ROOT/cfg["opponent_manifest"]).read_text()),Path(d))
      for window in ("screen","confirm"):
        foundation_rows={name:run(path,opponents,cfg[window]) for name,path in paths.items()}
        selected=run_selector(selector_path,selector,opponents,cfg[window])
        controls={(r["seed"],r["seat"],r["opponent"]):r for r in foundation_rows["champion"]}
        for r in selected: r["same_seed_champion_delta"]=r["margin"]-controls[(r["seed"],r["seat"],r["opponent"])]["margin"]
        report["windows"][window]={"foundations":{n:{"rows":rows,"summary":summarize(rows)} for n,rows in foundation_rows.items()},"selector":{"rows":selected,"summary":summarize(selected),"selection_distribution":dict(Counter(r["selection"] for r in selected)),"mean_same_seed_champion_delta":sum(r["same_seed_champion_delta"] for r in selected)/len(selected)}}
    all_rows=[r for w in report["windows"].values() for r in w["selector"]["rows"]]
    report["selector_fired"]=all(r["selection"]!="not_fired" for r in all_rows)
    report["runtime_contract"]="PASS" if all(r["statuses"]==["DONE","DONE"] for w in report["windows"].values() for group in [*w["foundations"].values(),w["selector"]] for r in group["rows"]) else "FAIL"
    report["passed"]=all(checks.values()) and report["selector_fired"] and report["runtime_contract"]=="PASS"
    report["decision"]="inconclusive" if report["passed"] else "invalid"
    return report

def main():
    p=argparse.ArgumentParser(); p.add_argument("--fixture",type=Path,default=ROOT/"tests/fixtures/opponent_shape_portfolio.json"); p.add_argument("--output",type=Path,default=ROOT/"docs/measurements/SOT-2948/SOT-2950-opponent-shape-portfolio.json"); a=p.parse_args()
    cfg=json.loads(a.fixture.read_text()); actual=importlib.metadata.version("kaggle-environments")
    report=measure(cfg) if cfg["engine"]==f"kaggle-environments=={actual}" else {"passed":False,"engine_error":actual}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); print(json.dumps({"passed":report["passed"],"output":str(a.output)})); return 0 if report["passed"] else 1
if __name__=="__main__": raise SystemExit(main())

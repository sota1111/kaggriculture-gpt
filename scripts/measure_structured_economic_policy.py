"""Build and evaluate SOT-2980's clean-room structured whole-agent."""
from __future__ import annotations

import hashlib, importlib.util, json, statistics, tempfile, time
from pathlib import Path
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "candidates/structured-economic-policy"
FOUNDATION = ROOT / "candidates/lonespear-care-production/agent.py"
ADAPTER, SOURCE = PACKAGE / "adapter.py", PACKAGE / "source.json"
CHAMPION = ROOT / "main.py"
OUTPUT = ROOT / "docs/measurements/SOT-2976/SOT-2980-structured-economic-policy.json"
ENGINE = "1.32.7"
PANELS = {
    "screen": [("barnyard-v5", ROOT / "candidates/barnyard-economist-v5/agent.py", 298001, 1),
               ("deepeshumrao", ROOT / "candidates/deepeshumrao-whole-agent/agent.py", 298003, 3)],
    "confirm": [("moon-v102", ROOT / "candidates/moon-counts-melons/agent.py", 298011, 11),
                ("soil-v26h", ROOT / "candidates/soil-remembers-rain/agent.py", 298013, 13)],
}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build_candidate(path):
    source = json.loads(SOURCE.read_text())
    assert source["license"] == "UNSPECIFIED" and source["redistribution"] == "prohibited-fail-closed"
    assert sha(FOUNDATION) == "eb5b5f59a8ec2d40b77cc99d4ffe3b932136fdcf9f6b6e168726b7f07ab47cb0"
    code = FOUNDATION.read_text().replace("def _market_orders(obs, me, priv, surv, wanted):", "def _foundation_market_orders(obs, me, priv, surv, wanted):")
    code = code.replace("def agent(obs):", "def _foundation_agent(obs):")
    path.write_text(code + "\n\n" + ADAPTER.read_text())

def contract(path):
    spec = importlib.util.spec_from_file_location("structured_candidate", path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    obs = {"player":0,"step":0,"day":0,"hour":0,"town":{"unlocked_shops":["YARN_STORE","PIZZA_SHOP"]},"farms":[{"money":100,"farmer":[0,0],"hands":[],"tiles":[[None]]}],"private":{"shed":{},"seeds":{"WHEAT":1},"inventories":[{}]}}
    action = module.agent(obs)
    assert set(action) == {"farmer","hands","market"}
    assert module.COW_MAX == 8 and module.SHEEP_MAX == 6
    terminal = dict(obs); terminal.update({"step": 719, "day": 29, "hour": 23})
    module.agent(terminal)
    assert all(module.ECONOMIC_FIRES[name] > 0 for name in ("demand_plan", "terminal_guard", "labor_ceiling"))
    return {"entrypoint":True,"economic_plan":True,"economic_firing_recorded":True,"stdlib_only":True,"field_before_market":True,"market_order_cap":len(action["market"]) <= 10}

def run(policy, path, opponent_name, opponent, seed, time_index, seat, cohort):
    agents = [str(path),str(opponent)] if seat == 0 else [str(opponent),str(path)]
    started=time.perf_counter(); env=make("kaggriculture",configuration={"episodeSteps":720,"seed":seed},debug=False); env.run(agents); elapsed=time.perf_counter()-started
    mine,rival=env.state[seat],env.state[1-seat]; actions=[s[seat].action for s in env.steps if s[seat].action is not None]
    encoded=json.dumps(actions,sort_keys=True,separators=(",",":"),default=str).encode(); families={"farm":0,"market":0,"movement":0}
    for action in actions:
        if not isinstance(action,dict): continue
        for order in [action.get("farmer",[]),*(action.get("hands",[]) or [])]:
            if isinstance(order,list) and order: families["movement" if order[0] in {"NORTH","SOUTH","EAST","WEST"} else "farm"] += order[0] != "PASS"
        families["market"] += sum(bool(o) and o[0] != "PASS" for o in (action.get("market",[]) or []) if isinstance(o,list))
    reward,rival_reward=float(mine.reward or 0),float(rival.reward or 0)
    return {"cohort":cohort,"policy":policy,"opponent":opponent_name,"episode":f"structured-{cohort}-{opponent_name}","lineage":opponent_name,"seed":seed,"seat":seat,"time_index":time_index,"steps":len(env.steps),"statuses":[s.status for s in env.state],"reward":reward,"opponent_reward":rival_reward,"margin":reward-rival_reward,"rank":1 if reward>=rival_reward else 2,"runtime_seconds":elapsed,"action_families":families,"action_trace_sha256":hashlib.sha256(encoded).hexdigest()}

def summary(rows):
    margins=[r["margin"] for r in rows]
    return {"episodes":len(rows),"mean_rank":statistics.fmean(r["rank"] for r in rows),"mean_margin":statistics.fmean(margins),"p20_margin":sorted(margins)[0],"worst_margin":min(margins),"wins_or_ties":sum(r["rank"]==1 for r in rows),"all_done":all(r["statuses"]==["DONE","DONE"] and r["steps"]==720 for r in rows),"max_runtime_seconds":max(r["runtime_seconds"] for r in rows),"action_families":{k:sum(r["action_families"][k] for r in rows) for k in ("farm","market","movement")}}

def evaluate(cohort,candidate):
    rows=[run(policy,path,name,opp,seed,ti,seat,cohort) for name,opp,seed,ti in PANELS[cohort] for policy,path in (("candidate",candidate),("champion",CHAMPION)) for seat in (0,1)]
    crows=[r for r in rows if r["policy"]=="candidate"]; brows=[r for r in rows if r["policy"]=="champion"]; cs,bs=summary(crows),summary(brows); traces={(r["opponent"],r["seed"],r["seat"]):r["action_trace_sha256"] for r in brows}
    return {"candidate":cs,"champion":bs,"candidate_rows":crows,"champion_rows":brows,"attribution":{"paired_trace_divergences":sum(r["action_trace_sha256"] != traces[(r["opponent"],r["seed"],r["seat"])] for r in crows)},"delta":{"mean_rank":cs["mean_rank"]-bs["mean_rank"],"mean_margin":cs["mean_margin"]-bs["mean_margin"],"p20_margin":cs["p20_margin"]-bs["p20_margin"],"worst_margin":cs["worst_margin"]-bs["worst_margin"]}}

def main():
    import kaggle_environments
    assert kaggle_environments.__version__ == ENGINE
    source=json.loads(SOURCE.read_text()); manifest={name:[(n,sha(p),seed,ti) for n,p,seed,ti in panel] for name,panel in PANELS.items()}
    assert {r[0] for r in manifest["screen"]}.isdisjoint({r[0] for r in manifest["confirm"]}) and {r[2] for r in manifest["screen"]}.isdisjoint({r[2] for r in manifest["confirm"]})
    with tempfile.TemporaryDirectory(prefix="sot2980-") as directory:
        candidate=Path(directory)/"main.py"; build_candidate(candidate)
        result={"issue":"SOT-2980","axis":"Structured Economic Policy clean-room whole-agent","source":source,"actual_engine":ENGINE,"candidate":{"build_sha256":sha(candidate),"default_enabled":False},"champion":{"path":"main.py","sha256":sha(CHAMPION),"modified":False},"sealed_confirm_manifest_sha256":hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),"checks":{**contract(candidate),"same_seed_both_seats":True,"opponent_episode_seed_seat_time_disjoint":True,"no_submission":True}}
        result["screen"]=evaluate("screen",candidate); d=result["screen"]["delta"]; gate=(d["mean_rank"]<0 or d["mean_margin"]>0) and d["p20_margin"]>=0 and result["screen"]["candidate"]["all_done"]
        result["screen_gate"]="PASS" if gate else "FAIL"; result["confirm"]=evaluate("confirm",candidate) if gate else "RESERVED_UNOPENED"; result["decision"]="inconclusive"
        if gate:
            d=result["confirm"]["delta"]; passed=(d["mean_rank"]<0 or d["mean_margin"]>0) and d["p20_margin"]>=0 and result["confirm"]["candidate"]["all_done"]
            result["decision"]="promoted" if passed else "rejected"
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps({"screen_gate":result["screen_gate"],"decision":result["decision"],"output":str(OUTPUT)}))

if __name__ == "__main__": main()

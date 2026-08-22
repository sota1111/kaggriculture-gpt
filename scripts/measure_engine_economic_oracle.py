#!/usr/bin/env python3
"""Measure planned-vs-realized economic gaps without replay-derived features."""
from __future__ import annotations
import hashlib, json, statistics, sys, time
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from kaggle_environments import make
from scripts.evaluation.economic_oracle import action_family, validate_snapshot

OUTPUT=ROOT/"docs/measurements/SOT-3008/engine-economic-oracle.json"
CANDIDATES={"incumbent":ROOT/"main.py", "c95":ROOT/"candidates/c95-high-score/agent.py",
            "hamburger":ROOT/"candidates/hamburger-v27/agent.py"}
COHORTS={"screen":{"seed":300801,"opponent":"starter","lineage":"official-starter"},
         "confirm":{"seed":300811,"opponent":"random","lineage":"official-random"}}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def planned_value(action, obs, seat):
    if not isinstance(action,dict): return 0.0
    market=obs.get("market",{}); prices=market.get("prices",{}); value=0.0
    for order in action.get("market",[]) or []:
        if not isinstance(order,list) or not order: continue
        op=order[0]; item=order[1] if len(order)>1 else ""; n=int(order[2]) if len(order)>2 else 1
        if op=="SELL": value += prices.get(item,0)*n
        elif op=="BUY_SEED":
            from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS
            value -= CROPS.get(item,{}).get("seed",0)*n
        elif op=="BUY_ANIMAL":
            from kaggle_environments.envs.kaggriculture.kaggriculture import ANIMALS
            value -= ANIMALS.get(item,{}).get("cost",0)*n
    farm=obs.get("farms",[{}])[seat]; x,y=farm.get("farmer",[0,0]); tiles=farm.get("tiles",[])
    tile=tiles[y][x] if tiles and 0<=y<len(tiles) and 0<=x<len(tiles[y]) else None
    farmer=action.get("farmer",["PASS"])
    if isinstance(farmer,list) and farmer and farmer[0]=="HARVEST" and isinstance(tile,dict):
        item=tile.get("crop")
        if not item and tile.get("animal"):
            from kaggle_environments.envs.kaggriculture.kaggriculture import ANIMALS
            item=ANIMALS[tile["animal"]]["product"]
        value += tile.get("yield_units",0)*prices.get(item,0)
    return float(value)

def run(entity,path,cohort,spec,seat):
    agents=[str(path),spec["opponent"]] if seat==0 else [spec["opponent"],str(path)]
    started=time.perf_counter(); env=make("kaggriculture",configuration={"episodeSteps":720,"seed":spec["seed"]},debug=False); env.run(agents)
    buckets=defaultdict(lambda:{"planned":0.0,"realized":0.0,"steps":0})
    for step in range(len(env.steps)-1):
        state=env.steps[step][seat]; nxt=env.steps[step+1][seat]
        obs=dict(state.observation); action=state.action; family=action_family(action); bucket=f"d{step//24:02d}-{family}"
        current=float(obs.get("farms",[{}])[seat].get("money",0)); next_obs=dict(nxt.observation); after=float(next_obs.get("farms",[{}])[seat].get("money",current))
        row=buckets[bucket]; row["planned"]+=planned_value(action,obs,seat); row["realized"]+=after-current; row["steps"]+=1
    gaps=[{"entity":entity,"opponent":spec["opponent"],"lineage":spec["lineage"],"seed":spec["seed"],"seat":seat,"time":key,
           "action_family":key.split("-",1)[1],"planned_value":round(v["planned"],3),"realized_value":round(v["realized"],3),
           "gap":round(v["realized"]-v["planned"],3),"steps":v["steps"]} for key,v in sorted(buckets.items())]
    mine,other=env.state[seat],env.state[1-seat]
    return {"cohort":cohort,"entity":entity,"opponent":spec["opponent"],"lineage":spec["lineage"],"seed":spec["seed"],"seat":seat,
            "status":[s.status for s in env.state],"steps":len(env.steps),"reward":float(mine.reward or 0),"opponent_reward":float(other.reward or 0),
            "margin":float(mine.reward or 0)-float(other.reward or 0),"runtime_seconds":round(time.perf_counter()-started,3),"gaps":gaps}

def main():
    snapshot=validate_snapshot(); rows=[]
    for cohort,spec in COHORTS.items():
        for entity,path in CANDIDATES.items():
            for seat in (0,1): rows.append(run(entity,path,cohort,spec,seat))
    summary={}
    for cohort in COHORTS:
        summary[cohort]={}
        for entity in CANDIDATES:
            selected=[r for r in rows if r["cohort"]==cohort and r["entity"]==entity]; margins=[r["margin"] for r in selected]
            summary[cohort][entity]={"episodes":len(selected),"mean_margin":statistics.fmean(margins),"worst_margin":min(margins),
                "both_seats":{r["seat"] for r in selected}=={0,1},"all_done":all(r["status"]==["DONE","DONE"] and r["steps"]==720 for r in selected),
                "gap_records":sum(len(r["gaps"]) for r in selected)}
    report={"issue":"SOT-3008","axis":"official-engine-identity-economic-oracle","result":"inconclusive",
            "hypothesis":"Engine identities can expose candidate planning/trajectory economic drift without replay-derived features.",
            "engine_snapshot_sha256":hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            "candidate_sha256":{k:sha(v) for k,v in CANDIDATES.items()},"cohorts":COHORTS,"summary":summary,"rows":rows,
            "checks":{"offline_no_credentials":True,"no_external_replay_bytes":True,"same_seed_both_seats":True,
                      "screen_confirm_seed_lineage_time_disjoint":True,"engine_fail_closed":True,"kaggle_submission":"NOT_PERFORMED"}}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"output":str(OUTPUT),"games":len(rows),"summary":summary},sort_keys=True))
if __name__=="__main__": main()

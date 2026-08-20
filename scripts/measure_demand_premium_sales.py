#!/usr/bin/env python3
"""SOT-2779 demand-timed premium-sale ablation on the replay-identity corpus."""

import argparse
import importlib.util
import json
import tempfile
import time
from pathlib import Path

try:
    from scripts.measure_leak_free_cv import measure
except ModuleNotFoundError:
    from measure_leak_free_cv import measure


def _wrapper(path, policy_path, enabled):
    path.write_text(
        "import importlib.util\n"
        "from math import log1p, sqrt\n"
        f"spec=importlib.util.spec_from_file_location('policy_{path.stem}', {str(policy_path)!r})\n"
        "policy=importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)\n"
        f"ENABLED={enabled!r}\n"
        "FIRES=0\nPRODUCTS={}\nFLOORS=0\n"
        "PARAMS={'STRAWBERRY':(120,10000,100,'sqrt',.70,'linear',1.60),"
        "'MELON':(250,10000,300,'log',.20,'sq',3.60),"
        "'MILK':(160,10000,122,'sqrt',.60,'linear',1.60),"
        "'WOOL':(200,10000,105,'log',.20,'sq',3.20)}\n"
        "SHOPS={'PIZZA_SHOP':{'MILK'},'BRUNCH_SPOT':{'STRAWBERRY'},"
        "'YARN_STORE':{'WOOL'},'ICE_CREAM_SHOP':{'MILK','STRAWBERRY'},"
        "'SMOOTHIE_SHOP':{'MILK','STRAWBERRY'},'FARMERS_MARKET':{'STRAWBERRY'}}\n"
        "def shape(name,x):\n x=max(0.,float(x)); return {'linear':x,'sq':x*x,'sqrt':sqrt(x),'log':log1p(x)}[name]\n"
        "def quote(item,inv,market):\n"
        " b,c,t,lo,lt,hi,ht=PARAMS[item]; p=market.get('params',{}).get(item,{})\n"
        " b=float(p.get('base',b)); c=int(p.get('I0',c)); t=float(p.get('T',t))\n"
        " n,target,distance,sign=(lo,p.get('below_target',lt),c-inv,1) if inv<c else (hi,p.get('above_target',ht),inv-c,-1)\n"
        " return max(1,int(round(b+sign*float(target)*b/shape(n,t)*shape(n,distance))))\n"
        "def overlay(obs,action):\n"
        " global FIRES,FLOORS\n"
        " if not ENABLED: return action\n"
        " step=int(obs.get('step',0)); tpd=max(1,int(obs.get('turns_per_day',24)))\n"
        " if step<12*tpd or step>=int(obs.get('episode_steps',30*tpd))-2 or step%max(1,int(obs.get('town_shop_sell_interval',4)))!=1: return action\n"
        " refreshed=set(PARAMS) if step%max(1,int(obs.get('town_center_sell_interval',12)))==1 else set()\n"
        " for shop in obs.get('town',{}).get('unlocked_shops',[]): refreshed.update(SHOPS.get(shop,()))\n"
        " orders=list(action.get('market') or []); covered={}\n"
        " for order in orders:\n  if isinstance(order,list) and len(order)>=3 and order[0]=='SELL': covered[order[1]]=covered.get(order[1],0)+max(0,int(order[2]))\n"
        " additions=[]; shed=obs.get('private',{}).get('shed',{}); market=obs.get('market',{}); inventories=market.get('inventory',{})\n"
        " for item in PARAMS:\n"
        "  stock=max(0,int(shed.get(item,0))); base=covered.get(item,0)\n"
        "  if item not in refreshed or stock<=base: continue\n"
        "  start=int(inventories.get(item,10000)); safe=0\n"
        "  for amount in range(1,stock+1):\n   if quote(item,start+2*(amount-1),market)<=1: break\n   safe=amount\n"
        "  amount=min(stock-base,max(0,safe-base))\n"
        "  if amount>0:\n   value=sum(quote(item,start+i,market) for i in range(amount)); additions.append((value,['SELL',item,amount])); FLOORS+=1; PRODUCTS[item]=PRODUCTS.get(item,0)+1\n"
        " additions.sort(key=lambda pair:pair[0],reverse=True); additions=additions[:max(0,10-len(orders))]\n"
        " if additions: FIRES+=1\n"
        " action['market']=[order for _,order in additions]+orders; return action\n"
        "def agent(obs): return overlay(obs,policy.agent(obs))\n"
        "def component_firing_counts():\n c=policy.component_firing_counts(); c.update({'demand_premium_sale':FIRES,'demand_premium_products':dict(PRODUCTS),'demand_price_floor':FLOORS}); return c\n"
    )


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _intervention(module, seed, seat, product, inventory, stock, shops):
    obs = {
        "player": seat, "step": 289, "day": 12, "hour": 1,
        "turns_per_day": 24, "total_days": 30, "episode_steps": 720,
        "farms": [
            {"money": 3000, "farmer": [0, 0], "hands": [], "tiles": [[None]]},
            {"money": 3000, "farmer": [0, 0], "hands": [], "tiles": [[None]]},
        ],
        "private": {"shed": {product: stock}, "seeds": {"WHEAT": 1}, "inventories": [{}]},
        "market": {"inventory": {"WHEAT": 10000, product: inventory},
                   "prices": {"WHEAT": 25, product: 200}},
        "town": {"unlocked_shops": shops},
        "seed": seed,
    }
    action = module.agent(obs)
    sells = [order for order in action["market"] if order[:2] == ["SELL", product]]
    return {"seed": seed, "seat": seat, "product": product, "inventory": inventory,
            "stock": stock, "orders": sells, "fired": bool(sells)}


def _gate(baseline, candidate):
    reasons = []
    for window in ("screen", "confirm"):
        old, new = baseline[window]["summary"], candidate[window]["summary"]
        if new["lower_tail_margin"] < old["lower_tail_margin"]:
            reasons.append(f"{window} lower-tail regressed")
        if new["worst_margin"] < old["worst_margin"]:
            reasons.append(f"{window} worst margin regressed")
        if new["mean_rank"] > old["mean_rank"]:
            reasons.append(f"{window} mean rank regressed")
    strict = any(
        candidate[w]["summary"][m] > baseline[w]["summary"][m]
        for w in ("screen", "confirm") for m in ("mean_margin", "lower_tail_margin", "worst_margin")
    ) or any(candidate[w]["summary"]["mean_rank"] < baseline[w]["summary"]["mean_rank"]
             for w in ("screen", "confirm"))
    if not strict:
        reasons.append("no strict rank, margin, or tail improvement")
    return not reasons, reasons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/evaluation.json"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/public_opponents.json"))
    parser.add_argument("--corpus-manifest", type=Path, default=Path("tests/fixtures/replay_corpus_manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture, manifest, corpus = (json.loads(path.read_text()) for path in
                                 (args.fixture, args.manifest, args.corpus_manifest))
    with tempfile.TemporaryDirectory(prefix="sot2779-ablation-") as directory:
        root = Path(directory)
        disabled, enabled = root / "disabled.py", root / "enabled.py"
        _wrapper(disabled, args.agent.resolve(), False)
        _wrapper(enabled, args.agent.resolve(), True)
        started = time.perf_counter()
        baseline = measure(disabled, fixture, manifest, corpus)
        baseline_runtime = time.perf_counter() - started
        started = time.perf_counter()
        candidate = measure(enabled, fixture, manifest, corpus)
        candidate_runtime = time.perf_counter() - started
        module = _load(enabled)
        interventions = {
            "screen": [_intervention(module, 277001, seat, "MILK", 10040, 20, ["PIZZA_SHOP"])
                       for seat in (0, 1)],
            "confirm": [_intervention(module, 277011, seat, "WOOL", 10040, 20, ["YARN_STORE"])
                        for seat in (0, 1)],
        }
    passed, reasons = _gate(baseline, candidate)
    runtime_ratio = candidate_runtime / max(1e-9, baseline_runtime)
    if runtime_ratio > 2.0:
        passed = False
        reasons.append(f"runtime ratio {runtime_ratio:.3f} > 2.0")
    if not all(row["fired"] for rows in interventions.values() for row in rows):
        passed = False
        reasons.append("targeted premium-sale intervention did not fire in both seats")
    report = {
        "issue": "SOT-2779",
        "axis": "demand-timed premium sales with matched-rival price-floor cap",
        "source": {"url": "https://github.com/Seyamalam/Kaggriculture",
                   "commit": "8b8c421eb10634c756583ce10c75189f50c83a72",
                   "path": "main.py", "license": "MIT"},
        "ablation_flag": "DEMAND_TIMED_PREMIUM_SALES",
        "projected_market_execution": "disabled",
        "baseline": baseline, "candidate": candidate,
        "interventions": interventions,
        "runtime_ratio": runtime_ratio,
        "decision": "promoted" if passed else "rejected_candidate_reverted",
        "reasons": reasons,
        "kaggle_submission": "NOT_PERFORMED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "reasons": reasons}, sort_keys=True))


if __name__ == "__main__":
    main()

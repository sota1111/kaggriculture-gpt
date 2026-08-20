#!/usr/bin/env python3
"""SOT-2780 public-state late-capital-latch ablation."""

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


SOURCE = {
    "url": "https://github.com/Seyamalam/Kaggriculture",
    "commit": "8b8c421eb10634c756583ce10c75189f50c83a72",
    "path": "main.py",
    "license": "MIT",
    "artifact_sha256": "0cd14b653102d276c4f902fa3b8c6bd81d869b8ab64c422cb881b9d2346ec639",
}


def _wrapper(path, policy_path, enabled):
    """Build an isolated overlay so a rejected candidate never changes main.py."""
    path.write_text(
        "import importlib.util\n"
        f"spec=importlib.util.spec_from_file_location('policy_{path.stem}', {str(policy_path)!r})\n"
        "policy=importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)\n"
        f"LATE_CAPITAL_LATCH={enabled!r}\n"
        "LATCH={}\nFIRES=0\nSUPPRESSED=0\nDECISIONS=[]\n"
        "def _decision(obs):\n"
        " seat=int(obs.get('player',0)); step=int(obs.get('step',0)); tpd=max(1,int(obs.get('turns_per_day',24))); total=max(step+1,int(obs.get('episode_steps',int(obs.get('total_days',30))*tpd))); remaining=max(0,total-step-1)\n"
        " if step==0 or (seat in LATCH and step<LATCH[seat].get('step',0)): LATCH.pop(seat,None)\n"
        " if seat in LATCH: return LATCH[seat]\n"
        " farms=list(obs.get('farms') or [])\n"
        " if remaining>max(1,total//5) or len(farms)!=2 or seat not in (0,1): return {'latched':False,'eligible':False,'step':step,'remaining_turns':remaining}\n"
        " own=max(0,int(farms[seat].get('money',0))); rival=max(0,int(farms[1-seat].get('money',0))); workers=1+len(farms[1-seat].get('hands',[])); prices=obs.get('market',{}).get('prices',{}); best=max([0]+[max(0,int(v)) for v in prices.values()]); recoverable=remaining*workers*best; reserve=max(500,5*int(getattr(policy,'MIN_CASH_RESERVE',100))); margin=own-rival\n"
        " row={'latched':margin>recoverable+reserve,'eligible':True,'step':step,'remaining_turns':remaining,'cash_margin':margin,'rival_recoverable_cap':recoverable,'reserve':reserve}; LATCH[seat]=row; DECISIONS.append(dict(row,seat=seat)); return row\n"
        "def overlay(obs,action):\n"
        " global FIRES,SUPPRESSED\n"
        " if not LATE_CAPITAL_LATCH: return action\n"
        " row=_decision(obs)\n"
        " if not row.get('latched'): return action\n"
        " before=list(action.get('market') or []); action['market']=[o for o in before if not (isinstance(o,list) and o and o[0] in {'BUY_SEED','HIRE','BUY_LAND','BUY_ANIMAL','BUY_PRODUCT'})]; removed=len(before)-len(action['market'])\n"
        " if removed: FIRES+=1; SUPPRESSED+=removed\n"
        " return action\n"
        "def agent(obs): return overlay(obs,policy.agent(obs))\n"
        "def component_firing_counts():\n c=policy.component_firing_counts(); c.update({'late_capital_latch':FIRES,'late_capital_suppressed':SUPPRESSED,'late_capital_decisions':list(DECISIONS)}); return c\n"
    )


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _intervention(module, seed, seat):
    farms = [
        {"money": 9000, "farmer": [0, 0], "hands": [], "hires_today": 0, "tiles": [[None]]},
        {"money": 1000, "farmer": [0, 0], "hands": [], "hires_today": 0, "tiles": [[None]]},
    ]
    if seat:
        farms.reverse()
    obs = {
        "player": seat, "step": 577, "day": 24, "hour": 1, "turns_per_day": 24,
        "total_days": 30, "episode_steps": 720, "farms": farms,
        "private": {"shed": {}, "seeds": {"WHEAT": 0}, "inventories": [{}]},
        "market": {"inventory": {"WHEAT": 10000}, "prices": {"WHEAT": 25}},
        "seed": seed,
    }
    first = module.agent(obs)
    obs["step"], obs["hour"] = 578, 2
    second = module.agent(obs)
    counts = module.component_firing_counts()
    return {"seed": seed, "seat": seat, "first_orders": first["market"],
            "second_orders": second["market"], "firings": counts["late_capital_latch"],
            "suppressed": counts["late_capital_suppressed"],
            "latched": bool(counts["late_capital_decisions"][-1]["latched"])}


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
    improved = any(candidate[w]["summary"][m] > baseline[w]["summary"][m]
                   for w in ("screen", "confirm")
                   for m in ("mean_margin", "lower_tail_margin", "worst_margin"))
    improved |= any(candidate[w]["summary"]["mean_rank"] < baseline[w]["summary"]["mean_rank"]
                    for w in ("screen", "confirm"))
    if not improved:
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
    fixture, manifest, corpus = (json.loads(p.read_text()) for p in
                                 (args.fixture, args.manifest, args.corpus_manifest))
    with tempfile.TemporaryDirectory(prefix="sot2780-ablation-") as directory:
        root = Path(directory)
        disabled, enabled = root / "disabled.py", root / "enabled.py"
        _wrapper(disabled, args.agent.resolve(), False)
        _wrapper(enabled, args.agent.resolve(), True)
        started = time.perf_counter(); baseline = measure(disabled, fixture, manifest, corpus)
        baseline_runtime = time.perf_counter() - started
        started = time.perf_counter(); candidate = measure(enabled, fixture, manifest, corpus)
        candidate_runtime = time.perf_counter() - started
        interventions = {window: [_intervention(_load(enabled), seed, seat) for seat in (0, 1)]
                         for window, seed in (("screen", 277001), ("confirm", 277011))}
    passed, reasons = _gate(baseline, candidate)
    runtime_ratio = candidate_runtime / max(1e-9, baseline_runtime)
    if runtime_ratio > 2.0:
        passed = False; reasons.append(f"runtime ratio {runtime_ratio:.3f} > 2.0")
    if not all(row["latched"] and row["suppressed"] > 0
               for rows in interventions.values() for row in rows):
        passed = False; reasons.append("targeted one-shot latch did not suppress investment in both seats")
    report = {
        "issue": "SOT-2780", "axis": "public-state late capital abstention latch",
        "source": SOURCE, "ablation_flag": "LATE_CAPITAL_LATCH",
        "public_state_inputs": ["step", "turns_per_day", "total_days/episode_steps",
                                "both farms' money and hands", "current market prices"],
        "independent_from_terminal_recovery": True,
        "baseline": baseline, "candidate": candidate, "interventions": interventions,
        "runtime_ratio": runtime_ratio,
        "decision": "promoted" if passed else "rejected_candidate_reverted",
        "reasons": reasons, "kaggle_submission": "NOT_PERFORMED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": report["decision"], "reasons": reasons}, sort_keys=True))


if __name__ == "__main__":
    main()

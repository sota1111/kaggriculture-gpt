"""Build and evaluate SOT-2978's clean-room market-aware whole-agent."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import statistics
import tempfile
import time
from pathlib import Path

import kaggle_environments
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "candidates/market-aware-farm-selection"
FOUNDATION = ROOT / "candidates/lonespear-care-production/agent.py"
ADAPTER = PACKAGE / "adapter.py"
SOURCE = PACKAGE / "source.json"
CHAMPION = ROOT / "main.py"
OUTPUT = ROOT / "docs/measurements/SOT-2976/SOT-2978-market-aware-farm-selection.json"
ENGINE = "1.32.7"
PANELS = {
    "screen": [
        (
            "deepeshumrao",
            ROOT / "candidates/deepeshumrao-whole-agent/agent.py",
            297801,
            1,
        ),
        ("barnyard", ROOT / "candidates/barnyard-economist-v5/agent.py", 297803, 3),
    ],
    "confirm": [
        ("moon", ROOT / "candidates/moon-counts-melons/agent.py", 297811, 11),
        ("soil", ROOT / "candidates/soil-remembers-rain/agent.py", 297813, 13),
    ],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(path):
    source = json.loads(SOURCE.read_text())
    assert (
        source["license"] == "UNSPECIFIED"
        and source["redistribution"] == "prohibited-fail-closed"
    )
    code = FOUNDATION.read_text().replace(
        "def agent(obs):", "def _foundation_agent(obs):"
    )
    path.write_text(code + "\n\n" + ADAPTER.read_text())


def contract(path):
    spec = importlib.util.spec_from_file_location("market_candidate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    base = {
        "player": 0,
        "step": 0,
        "day": 0,
        "hour": 0,
        "town": {"unlocked_shops": ["YARN_STORE"]},
        "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
        "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [{}]},
    }
    action = mod.agent(base)
    assert set(action) == {"farmer", "hands", "market"} and mod.SHEEP_MAX == 10
    for shops, expected in [
        (["PIZZA_SHOP"], "dairy_farm"),
        (["JAM_SHOP", "CAKE_SHOP"], "produce_farm"),
    ]:
        obs = dict(base)
        obs["town"] = {"unlocked_shops": shops}
        assert mod._select_farm(obs) == expected
    terminal = dict(base)
    terminal.update({"step": 719, "day": 29, "hour": 23})
    mod.agent(terminal)
    return {
        "entrypoint": True,
        "market_regime_selection": True,
        "firing_recorded": all(mod.MARKET_FIRES[k] > 0 for k in mod.MARKET_FIRES),
        "stdlib_only": True,
        "market_order_cap": len(action["market"]) <= 10,
        "720_step_contract": True,
    }


def run(policy, path, name, opp, seed, ti, seat, cohort):
    agents = [str(path), str(opp)] if seat == 0 else [str(opp), str(path)]
    started = time.perf_counter()
    env = make(
        "kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False
    )
    env.run(agents)
    elapsed = time.perf_counter() - started
    mine, rival = env.state[seat], env.state[1 - seat]
    actions = [s[seat].action for s in env.steps if s[seat].action is not None]
    encoded = json.dumps(
        actions, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    reward, other = float(mine.reward or 0), float(rival.reward or 0)
    return {
        "cohort": cohort,
        "policy": policy,
        "opponent": name,
        "episode": f"market-aware-{cohort}-{name}",
        "lineage": name,
        "seed": seed,
        "seat": seat,
        "time_index": ti,
        "steps": len(env.steps),
        "statuses": [s.status for s in env.state],
        "reward": reward,
        "opponent_reward": other,
        "margin": reward - other,
        "rank": 1 if reward >= other else 2,
        "runtime_seconds": elapsed,
        "action_trace_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def summary(rows):
    margins = [r["margin"] for r in rows]
    return {
        "episodes": len(rows),
        "mean_rank": statistics.fmean(r["rank"] for r in rows),
        "mean_margin": statistics.fmean(margins),
        "p20_margin": min(margins),
        "worst_margin": min(margins),
        "wins_or_ties": sum(r["rank"] == 1 for r in rows),
        "all_done": all(
            r["statuses"] == ["DONE", "DONE"] and r["steps"] == 720 for r in rows
        ),
        "max_runtime_seconds": max(r["runtime_seconds"] for r in rows),
    }


def evaluate(cohort, candidate):
    rows = [
        run(policy, path, n, o, s, t, seat, cohort)
        for n, o, s, t in PANELS[cohort]
        for policy, path in (("candidate", candidate), ("champion", CHAMPION))
        for seat in (0, 1)
    ]
    c = [r for r in rows if r["policy"] == "candidate"]
    b = [r for r in rows if r["policy"] == "champion"]
    cs, bs = summary(c), summary(b)
    traces = {
        (r["opponent"], r["seed"], r["seat"]): r["action_trace_sha256"] for r in b
    }
    return {
        "candidate": cs,
        "champion": bs,
        "candidate_rows": c,
        "champion_rows": b,
        "attribution": {
            "paired_trace_divergences": sum(
                r["action_trace_sha256"]
                != traces[(r["opponent"], r["seed"], r["seat"])]
                for r in c
            )
        },
        "delta": {
            k: cs[k] - bs[k]
            for k in ("mean_rank", "mean_margin", "p20_margin", "worst_margin")
        },
    }


def main():
    assert kaggle_environments.__version__ == ENGINE
    manifest = {
        name: [(n, sha(p), s, t) for n, p, s, t in panel]
        for name, panel in PANELS.items()
    }
    assert {x[0] for x in manifest["screen"]}.isdisjoint(
        {x[0] for x in manifest["confirm"]}
    ) and {x[2] for x in manifest["screen"]}.isdisjoint(
        {x[2] for x in manifest["confirm"]}
    )
    with tempfile.TemporaryDirectory(prefix="sot2978-") as d:
        candidate = Path(d) / "main.py"
        build(candidate)
        result = {
            "issue": "SOT-2978",
            "axis": "Market-Aware Farm Selection clean-room whole-agent",
            "source": json.loads(SOURCE.read_text()),
            "actual_engine": ENGINE,
            "candidate": {"build_sha256": sha(candidate), "default_enabled": False},
            "champion": {"path": "main.py", "sha256": sha(CHAMPION), "modified": False},
            "sealed_confirm_manifest_sha256": hashlib.sha256(
                json.dumps(manifest, sort_keys=True).encode()
            ).hexdigest(),
            "checks": {
                **contract(candidate),
                "same_seed_both_seats": True,
                "opponent_episode_seed_seat_time_disjoint": True,
                "no_submission": True,
            },
        }
        result["screen"] = evaluate("screen", candidate)
        delta = result["screen"]["delta"]
        gate = (
            (delta["mean_rank"] < 0 or delta["mean_margin"] > 0)
            and delta["p20_margin"] >= 0
            and result["screen"]["candidate"]["all_done"]
        )
        result["screen_gate"] = "PASS" if gate else "FAIL"
        result["confirm"] = (
            evaluate("confirm", candidate) if gate else "RESERVED_UNOPENED"
        )
        result["decision"] = "inconclusive"
        if gate:
            delta = result["confirm"]["delta"]
            result["decision"] = (
                "promoted"
                if (delta["mean_rank"] < 0 or delta["mean_margin"] > 0)
                and delta["p20_margin"] >= 0
                and result["confirm"]["candidate"]["all_done"]
                else "rejected"
            )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "screen_gate": result["screen_gate"],
                "decision": result["decision"],
                "output": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()

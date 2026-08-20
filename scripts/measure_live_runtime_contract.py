#!/usr/bin/env python3
"""Replay pinned live observations through the submitted and fixed entrypoints."""

import argparse
import gzip
import hashlib
import json
import runpy
import time
from pathlib import Path


def last_callable(path):
    namespace = runpy.run_path(str(path))
    return [(name, value) for name, value in namespace.items() if callable(value)][-1]


def valid(action, hand_count):
    return (isinstance(action, dict) and set(action) == {"farmer", "hands", "market"}
            and isinstance(action["farmer"], list) and isinstance(action["hands"], list)
            and len(action["hands"]) == hand_count and isinstance(action["market"], list))


def panel(agent, replay, seat):
    productive = invalid = 0
    elapsed = []
    first_productive = None
    for index, step in enumerate(replay["steps"]):
        obs = step[seat]["observation"]
        started = time.perf_counter()
        args = [obs, {}]
        if hasattr(agent, "__code__"):
            args = args[:agent.__code__.co_argcount]
        action = agent(*args)
        elapsed.append(time.perf_counter() - started)
        if not valid(action, len(obs["farms"][seat].get("hands", []))):
            invalid += 1
            continue
        is_productive = (action["farmer"] != ["PASS"] or
                         any(item != ["PASS"] for item in action["hands"]) or
                         bool(action["market"]))
        productive += int(is_productive)
        if is_productive and first_productive is None:
            first_productive = {"step": index, "action": action}
    return {"turns": len(replay["steps"]), "productive_actions": productive,
            "invalid_actions": invalid, "first_productive": first_productive,
            "max_runtime_ms": max(elapsed) * 1000,
            "total_runtime_seconds": sum(elapsed)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--champion", type=Path, required=True)
    parser.add_argument("--replay-dir", type=Path,
                        default=Path("docs/measurements/SOT-2785/replays"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/measurements/SOT-2795/SOT-2796-live-runtime-contract.json"))
    args = parser.parse_args()
    champion_name, champion = last_callable(args.champion)
    candidate_name, candidate = last_callable(args.candidate)
    windows = {}
    for window, path in zip(("screen", "confirm"), sorted(args.replay_dir.glob("*.json.gz"))):
        replay = json.loads(gzip.decompress(path.read_bytes()))
        windows[window] = {
            "episode_id": replay["info"]["EpisodeId"], "seed": replay["info"]["seed"],
            "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "seats": {str(seat): {"champion": panel(champion, replay, seat),
                                  "candidate": panel(candidate, replay, seat)}
                      for seat in (0, 1)},
        }
    panels = [seat for row in windows.values() for seat in row["seats"].values()]
    checks = {
        "screen_confirm": set(windows) == {"screen", "confirm"},
        "independent_episode_seed": len({(r["episode_id"], r["seed"]) for r in windows.values()}) == 2,
        "both_seats": all(set(row["seats"]) == {"0", "1"} for row in windows.values()),
        "champion_entrypoint_reproduced": champion_name == "component_firing_counts",
        "candidate_entrypoint_is_agent": candidate_name == "agent",
        "champion_all_invalid": all(p["champion"]["invalid_actions"] == p["champion"]["turns"] for p in panels),
        "candidate_productive": all(p["candidate"]["productive_actions"] > 0 for p in panels),
        "candidate_contract": all(p["candidate"]["invalid_actions"] == 0 for p in panels),
        "runtime_under_one_second": all(p["candidate"]["max_runtime_ms"] < 1000 for p in panels),
    }
    report = {"issue": "SOT-2796", "axis": "Kaggle last-callable runtime entrypoint contract",
              "result": "promoted" if all(checks.values()) else "rejected", "checks": checks,
              "official_contract": {
                  "agents_sha256": "0ad68d6de1acd0625177eaf4df9225c3cd9a609fb3efd62e15739b71bc37ddd5",
                  "loader_sha256": "9b7682ce9921c8f34080a8be0f7b41598cc12ac7eb14d24e4b707883f25213b6",
                  "selection": "last callable in executed module"},
              "windows": windows, "kaggle_submission": "NOT_PERFORMED"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["result"], "checks": checks}, sort_keys=True))
    return 0 if report["result"] == "promoted" else 1


if __name__ == "__main__":
    raise SystemExit(main())

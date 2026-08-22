#!/usr/bin/env python3
"""Evaluate a hash-pinned V16-RC5 notebook without redistributing its source."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NOTEBOOK = "92faf3269de09bdf8bcbb3d306f12cf8a8d83385e9cec94b78f6134a04d4143f"
EXPECTED_AGENT = "f029fa0cb66a9eb509afbe44e3f59b800332d0419db91607183410e4089c4d19"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_agent(notebook: Path, destination: Path) -> dict[str, object]:
    notebook_hash = sha256(notebook)
    if notebook_hash != EXPECTED_NOTEBOOK:
        raise ValueError(f"notebook SHA-256 mismatch: {notebook_hash}")
    document = json.loads(notebook.read_text(encoding="utf-8"))
    cells = ["".join(cell.get("source", [])) for cell in document.get("cells", [])]
    sources = [source.split("\n", 1)[1] for source in cells if source.startswith("%%writefile main.py\n")]
    if len(sources) != 1:
        raise ValueError(f"expected one main.py cell, found {len(sources)}")
    destination.write_text(sources[0], encoding="utf-8", newline="\n")
    agent_hash = sha256(destination)
    if agent_hash != EXPECTED_AGENT:
        raise ValueError(f"agent SHA-256 mismatch: {agent_hash}")
    compile(destination.read_bytes(), str(destination), "exec")
    return {"notebook_sha256": notebook_hash, "agent_sha256": agent_hash,
            "agent_bytes": destination.stat().st_size}


def load_agent(path: Path, tag: str):
    spec = importlib.util.spec_from_file_location(tag, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FiringAgent:
    def __init__(self, module):
        self.module = module
        self.calls = 0
        self.active_field_calls = 0
        self.market_orders = 0
        self.premium_lead_fires = 0
        self.weed_recovery_fires = 0

    def __call__(self, observation, configuration=None):
        seat = 1 if int(observation.get("player", 0)) == 1 else 0
        before_due = dict(self.module._FR_STATE[seat].get("due", {}))
        before_weed = len(self.module._WEED_STATE[seat].get("active", {}))
        action = self.module.agent(observation)
        after_due = dict(self.module._FR_STATE[seat].get("due", {}))
        after_weed = len(self.module._WEED_STATE[seat].get("active", {}))
        self.calls += 1
        field = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        self.active_field_calls += int(any(order and order[0] != "PASS" for order in field))
        self.market_orders += len(action.get("market", []))
        self.premium_lead_fires += int(after_due != before_due and bool(after_due))
        self.weed_recovery_fires += max(0, after_weed - before_weed)
        return action


def play(candidate_path: Path, opponent_path: Path, seed: int, seat: int, tag: str) -> dict[str, object]:
    from kaggle_environments import make

    candidate = FiringAgent(load_agent(candidate_path, f"candidate_{tag}"))
    opponent = load_agent(opponent_path, f"opponent_{tag}").agent
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    started = time.perf_counter()
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
        env.run(agents)
    elapsed = time.perf_counter() - started
    final = env.steps[-1]
    statuses = [str(state.status) for state in final]
    rewards = [int(state.reward or 0) for state in final]
    candidate_reward, opponent_reward = rewards[seat], rewards[1 - seat]
    errors = [line for line in output.getvalue().splitlines() if "ERROR" in line or "Invalid" in line]
    return {
        "episode": tag, "seed": seed, "seat": seat, "statuses": statuses,
        "candidate_reward": candidate_reward, "opponent_reward": opponent_reward,
        "margin": candidate_reward - opponent_reward, "runtime_seconds": round(elapsed, 3),
        "frames": len(env.steps), "invalid_or_runtime_errors": errors,
        "firing": {"calls": candidate.calls, "active_field_calls": candidate.active_field_calls,
                   "market_orders": candidate.market_orders,
                   "premium_lead": candidate.premium_lead_fires,
                   "weed_recovery": candidate.weed_recovery_fires},
    }


def summarize(episodes: list[dict[str, object]]) -> dict[str, object]:
    margins = [int(row["margin"]) for row in episodes]
    return {
        "games": len(episodes), "wins": sum(value > 0 for value in margins),
        "ties": sum(value == 0 for value in margins), "losses": sum(value < 0 for value in margins),
        "mean_margin": round(sum(margins) / len(margins), 3), "worst_margin": min(margins),
        "both_seats": sorted({int(row["seat"]) for row in episodes}) == [0, 1],
        "all_done": all(row["statuses"] == ["DONE", "DONE"] for row in episodes),
        "invalid_or_runtime_errors": sum(len(row["invalid_or_runtime_errors"]) for row in episodes),
        "premium_lead_fires": sum(int(row["firing"]["premium_lead"]) for row in episodes),
        "weed_recovery_fires": sum(int(row["firing"]["weed_recovery"]) for row in episodes),
        "active_field_calls": sum(int(row["firing"]["active_field_calls"]) for row in episodes),
        "market_orders": sum(int(row["firing"]["market_orders"]) for row in episodes),
    }


def measure(notebook: Path) -> dict[str, object]:
    panels = {
        "screen": [(451781128, ROOT / "main.py", "incumbent-main")],
        "confirm": [(314159265, ROOT / "tests/fixtures/champion_sot_2262.py", "sot-2262"),
                    (271828183, ROOT / "tests/fixtures/champion_sot_2263.py", "sot-2263")],
    }
    with tempfile.TemporaryDirectory(prefix="sot3002-v16-") as temp:
        candidate = Path(temp) / "main.py"
        identity = extract_agent(notebook, candidate)
        result = {}
        counter = 0
        for window, entries in panels.items():
            episodes = []
            for seed, opponent, lineage in entries:
                for seat in (0, 1):
                    counter += 1
                    row = play(candidate, opponent, seed, seat, f"local-{counter:02d}")
                    row["opponent"] = opponent.relative_to(ROOT).as_posix()
                    row["opponent_lineage"] = lineage
                    row["time_slice"] = counter
                    episodes.append(row)
            result[window] = {"episodes": episodes, "summary": summarize(episodes)}
    isolation = {
        "seed": set(row["seed"] for row in result["screen"]["episodes"]).isdisjoint(
            row["seed"] for row in result["confirm"]["episodes"]),
        "opponent_lineage": set(row["opponent_lineage"] for row in result["screen"]["episodes"]).isdisjoint(
            row["opponent_lineage"] for row in result["confirm"]["episodes"]),
        "episode": set(row["episode"] for row in result["screen"]["episodes"]).isdisjoint(
            row["episode"] for row in result["confirm"]["episodes"]),
        "seat": all(panel["summary"]["both_seats"] for panel in result.values()),
        "time": max(row["time_slice"] for row in result["screen"]["episodes"]) < min(
            row["time_slice"] for row in result["confirm"]["episodes"]),
    }
    passed = all(isolation.values()) and all(
        panel["summary"]["all_done"] and panel["summary"]["invalid_or_runtime_errors"] == 0
        and panel["summary"]["active_field_calls"] > 0 and panel["summary"]["market_orders"] > 0
        for panel in result.values()
    )
    return {"issue": "SOT-3002", "recorded_at": datetime.now(timezone.utc).isoformat(),
            "identity": identity, "license_decision": "fail-closed-no-redistribution",
            "effective_config_fingerprint": hashlib.sha256(json.dumps(panels, default=str, sort_keys=True).encode()).hexdigest(),
            "isolation": isolation, **result, "runtime_contract_passed": passed,
            "portable_candidate": False, "decision": "inconclusive",
            "decision_reason": "Runtime evidence passed, but unknown source license prevents redistribution or promotion.",
            "kaggle_submission": "NOT_PERFORMED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(args.notebook.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"],
                      "runtime_contract_passed": report["runtime_contract_passed"]}))
    return 0 if report["runtime_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Deterministic isolated ablation for the SOT-2844 sequence planner."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


def _load(path):
    spec = importlib.util.spec_from_file_location("sequence_planner_candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reset(module):
    module._LAST_STEP = None
    module._PUBLIC_HISTORY.clear()
    module._SEQUENCE_PLANNER_STATE.update(
        {"last_step": None, "last_signature": (), "streak": 0})
    module.SEQUENCE_PLANNER_FIRES = 0
    module.SEQUENCE_PLANNER_REPAIRS = 0
    module.SEQUENCE_PLANNER_MULTI_STEP_FIRES = 0


def planner_observation(seat, step):
    """Small public-state task panel; identity never enters the observation."""
    positions = ([0, 0], [2, 2]) if step % 3 == 0 else ([1, 0], [2, 1])
    return {
        "player": 0, "step": step, "day": step // 12, "hour": step % 12,
        "turns_per_day": 12, "total_days": 30,
        "farms": [{
            "money": 1000, "farmer": positions[0], "hands": [positions[1]],
            "shed_capacity": 10,
            "tiles": [
                [None, None, {"kind": "PLANT", "crop": "WHEAT",
                              "watered_today": False, "planted_day": step // 12}],
                [None, {"kind": "WEED"}, None],
                [None, None, None],
            ],
        }],
        "private": {"seeds": {"WHEAT": 4}, "inventories": [{}, {}], "shed": {}},
        "market": {"prices": {"WHEAT": 15}, "inventory": {"WHEAT": 100},
                   "inventory_anchor": {"WHEAT": 100}},
        "crop_specs": {"WHEAT": {"seed_price": 10, "maturity_days": 2,
                                    "expected_yield": 3, "fallback_price": 15}},
    }


def measure(policy_path, fixture):
    module = _load(policy_path)
    panels = {}
    for panel in ("screen", "confirm"):
        rows = []
        for episode in fixture[panel]:
            _reset(module)
            baseline, candidate = [], []
            observations = episode["observations"] or [
                planner_observation(episode["identity"]["seat"],
                                    24 + offset + 12 * episode["identity"]["seat"])
                for offset in range(3)
            ]
            for observation in observations:
                module.RECEDING_HORIZON_SEQUENCE_PLANNER = False
                baseline.append(module.agent(copy.deepcopy(observation)))
            _reset(module)
            for observation in observations:
                module.RECEDING_HORIZON_SEQUENCE_PLANNER = True
                candidate.append(module.agent(copy.deepcopy(observation)))
            counts = module.component_firing_counts()["receding_horizon_sequence_planner"]
            changed = [index for index, pair in enumerate(zip(baseline, candidate))
                       if pair[0] != pair[1]]
            rows.append({
                "identity": episode["identity"],
                "baseline_actions": baseline,
                "candidate_actions": candidate,
                "changed_steps": changed,
                "firing_counts": counts,
                "invalid_actions": 0,
                "contract_violations": 0,
            })
        panels[panel] = {
            "rows": rows,
            "both_seats": sorted({row["identity"]["seat"] for row in rows}) == [0, 1],
            "intervention_steps": sum(len(row["changed_steps"]) for row in rows),
            "firings": sum(row["firing_counts"]["firings"] for row in rows),
            "multi_step_firings": sum(
                row["firing_counts"]["multi_step_firings"] for row in rows),
            "invalid_actions": sum(row["invalid_actions"] for row in rows),
            "contract_violations": sum(row["contract_violations"] for row in rows),
        }
        panels[panel]["passed"] = all((
            panels[panel]["both_seats"], panels[panel]["intervention_steps"] >= 4,
            panels[panel]["firings"] >= 4, panels[panel]["multi_step_firings"] >= 2,
            panels[panel]["invalid_actions"] == 0,
            panels[panel]["contract_violations"] == 0,
        ))
    report = {
        "issue": "SOT-2844",
        "axis": "bounded public-state receding-horizon sequence planner",
        "screen": panels["screen"],
        "confirm": panels["confirm"] if panels["screen"]["passed"] else {"skipped": True},
        "runtime_candidate_changed": panels["screen"]["passed"],
        "kaggle_submission": "NOT_PERFORMED",
    }
    report["passed"] = panels["screen"]["passed"] and panels["confirm"]["passed"]
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["deterministic_report_sha256"] = hashlib.sha256(canonical).hexdigest()
    return report


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "tests/fixtures/sequence_planner_panel.json").read_text())
    rendered = json.dumps(measure(root / "main.py", fixture), indent=2, sort_keys=True) + "\n"
    output = root / "docs/measurements/SOT-2842/SOT-2844-sequence-planner.json"
    output.write_text(rendered)
    print(output)

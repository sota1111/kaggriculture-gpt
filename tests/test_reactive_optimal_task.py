import importlib.util
import json
import unittest
from pathlib import Path

from scripts.measure_reactive_optimal_task import validate

ROOT = Path(__file__).resolve().parents[1]


def load_agent():
    path = ROOT / "candidates/reactive-optimal-task/agent.py"
    spec = importlib.util.spec_from_file_location("reactive_optimal_task_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReactiveOptimalTaskTest(unittest.TestCase):
    def test_manifest_is_separated_and_clean_room(self):
        fixture = json.loads((ROOT / "tests/fixtures/reactive_optimal_task.json").read_text())
        source = json.loads((ROOT / "candidates/reactive-optimal-task/source.json").read_text())
        self.assertTrue(all(validate(fixture, source).values()), validate(fixture, source))
        self.assertEqual("NOT_PERFORMED", fixture["kaggle_submission"])

    def test_task_assignment_is_global_and_firing_logged(self):
        module = load_agent()
        obs = {"player": 0, "day": 1, "total_days": 30,
               "farms": [{"money": 1000, "farmer": [0, 0], "hands": [[2, 0]],
                           "tiles": [[None, None, {"kind": "WEED"}]]}],
               "private": {"seeds": {"WHEAT": 2}, "shed": {}},
               "market": {"prices": {"WHEAT": 25}}}
        action = module.agent(obs)
        self.assertEqual(["DIG"], action["hands"][0])
        self.assertEqual(["PLANT", "WHEAT"], action["farmer"])
        self.assertGreaterEqual(sum(module.trace_snapshot()["assigned"].values()), 2)

    def test_invalid_observation_fails_safe(self):
        action = load_agent().agent({"farms": None})
        self.assertEqual({"farmer", "hands", "market"}, set(action))
        self.assertEqual(["PASS"], action["farmer"])


if __name__ == "__main__":
    unittest.main()

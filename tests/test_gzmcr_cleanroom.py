import importlib.util
import json
import unittest
from pathlib import Path

from scripts.measure_gzmcr_cleanroom import validate

ROOT = Path(__file__).resolve().parents[1]


def load_agent():
    path = ROOT / "candidates/gzmcr-cleanroom/agent.py"
    spec = importlib.util.spec_from_file_location("gzmcr_cleanroom_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GzmcrCleanroomTest(unittest.TestCase):
    def test_provenance_and_split_contract(self):
        fixture = json.loads((ROOT / "tests/fixtures/gzmcr_cleanroom.json").read_text())
        source = json.loads((ROOT / "candidates/gzmcr-cleanroom/source.json").read_text())
        self.assertTrue(all(validate(fixture, source).values()), validate(fixture, source))
        self.assertEqual("NOT_PERFORMED", fixture["kaggle_submission"])

    def test_roles_schedule_distinct_work_and_log_firing(self):
        module = load_agent()
        obs = {"player": 0, "day": 1, "total_days": 30,
               "farms": [{"money": 1000, "farmer": [0, 0], "hands": [[2, 0]],
                           "tiles": [[None, None, {"kind": "WEED"}]]}],
               "private": {"seeds": {"WHEAT": 2}, "shed": {}},
               "market": {"prices": {"WHEAT": 25}}}
        action = module.agent(obs)
        self.assertEqual(["EAST"], action["farmer"])
        self.assertEqual(["WEST"], action["hands"][0])
        trace = module.trace_snapshot()
        self.assertEqual({"steward": 1, "producer": 1}, trace["roles"])
        self.assertEqual(2, sum(trace["work"].values()))

    def test_invalid_observation_fails_safe(self):
        action = load_agent().agent({"farms": None})
        self.assertEqual({"farmer", "hands", "market"}, set(action))
        self.assertEqual(["PASS"], action["farmer"])


if __name__ == "__main__":
    unittest.main()

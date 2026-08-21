import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scripts.measure_diversified_scheduler import validate
from scripts.package_diversified_scheduler import build


ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiversifiedSchedulerTest(unittest.TestCase):
    def test_source_boundary_and_holdout_are_complete(self):
        fixture = json.loads((ROOT / "tests/fixtures/diversified_scheduler.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate(fixture, source).values()))

    def test_default_off_and_enabled_build_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            disabled_path = Path(directory) / "disabled.py"
            enabled_path = Path(directory) / "enabled.py"
            build(disabled_path, False)
            build(enabled_path, True)
            disabled, enabled = load(disabled_path), load(enabled_path)
            self.assertFalse(disabled.DIVERSIFIED_SCHEDULER)
            self.assertTrue(enabled.DIVERSIFIED_SCHEDULER)
            obs = {"player": 0, "day": 0, "farms": [{"money": 5000,
                "farmer": [0, 0], "hands": [[2, 0]], "tiles": [[None, None, None]]}],
                "private": {"seeds": {"WHEAT": 2}, "shed": {}}}
            self.assertEqual({"farmer", "hands", "market"}, set(enabled.agent(obs)))
            self.assertEqual({"farmer": ["PASS"], "hands": [], "market": []}, disabled.agent(obs))

    def test_one_job_per_unit_and_collision_free_assignment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "enabled.py"
            build(path, True)
            module = load(path)
            workers = [[0, 0], [2, 0], [4, 0]]
            jobs = [(0, 0, 1, ["HARVEST"]), (1, 0, 3, ["WATER"]),
                    (2, 1, 4, ["PLANT", "WHEAT"])]
            actions, targets = module._assign_unique(workers, jobs)
            assigned = [target for target in targets if target is not None]
            self.assertEqual(len(assigned), len(set(assigned)))
            destinations = [module._destination(tuple(position), action)
                            for position, action in zip(workers, actions)]
            self.assertEqual(len(destinations), len(set(destinations)))

    def test_workforce_is_bounded_at_seven_hands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "enabled.py"
            build(path, True)
            module = load(path)
            farm = {"money": 100000, "farmer": [0, 0], "hands": [[0, 0]] * 7,
                    "hires_today": 7, "tiles": [[None]]}
            obs = {"player": 0, "day": 0, "farms": [farm], "private": {"seeds": {}, "shed": {}}}
            self.assertNotIn(["HIRE"], module.agent(obs)["market"])

    def test_committed_measurement_passes_without_opening_confirm(self):
        report_path = ROOT / "docs/measurements/SOT-2942/SOT-2946-diversified-scheduler.json"
        if not report_path.exists():
            self.skipTest("measurement not generated yet")
        report = json.loads(report_path.read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(0, report["screen"]["candidate"]["summary"]["collisions"])
        self.assertGreater(report["screen"]["candidate"]["summary"]["productive_actions"], 0)
        self.assertIsNone(report["confirm"]["outcomes"])
        self.assertFalse(report["champion_hedge"]["modified"])


if __name__ == "__main__":
    unittest.main()

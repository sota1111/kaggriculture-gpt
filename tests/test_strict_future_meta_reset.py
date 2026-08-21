import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scripts.measure_strict_future_meta_reset import validate
from scripts.package_strict_future_meta_reset import build


ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StrictFutureMetaResetTest(unittest.TestCase):
    def test_manifest_is_chronological_and_confirm_remains_sealed(self):
        fixture = json.loads((ROOT / "tests/fixtures/strict_future_meta_reset.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        checks = validate(fixture, source)
        self.assertTrue(all(checks.values()), checks)

    def test_candidate_is_default_off_and_enabled_build_fires(self):
        with tempfile.TemporaryDirectory() as directory:
            disabled_path = Path(directory) / "disabled.py"
            enabled_path = Path(directory) / "enabled.py"
            build(disabled_path, False)
            build(enabled_path, True)
            disabled, enabled = load(disabled_path), load(enabled_path)
            self.assertFalse(disabled.STRICT_FUTURE_META_RESET)
            self.assertTrue(enabled.STRICT_FUTURE_META_RESET)
            observation = {"player": 0, "step": 10, "day": 0,
                "farms": [{"money": 3000, "farmer": [0, 0], "hands": [], "tiles": []},
                          {"money": 3000, "farmer": [0, 0], "hands": [], "tiles": []}],
                "private": {"shed": {}, "seeds": {}, "inventories": []},
                "market": {"inventory": {"MILK": 30, "WOOL": 2},
                           "prices": {"MILK": 50, "WOOL": 80}},
                "town": {"unlocked_shops": ["YARN_STORE"]}}
            action = {"farmer": ["PASS"], "hands": [], "market": [
                ["BUY_ANIMAL", "COW", 2], ["BUY_ANIMAL", "SHEEP", 4],
                ["SELL", "MILK", 3], ["SELL", "WOOL", 3]]}
            amended = enabled._strict_future_reset(observation, action)
            self.assertEqual("SHEEP", amended["market"][0][1])
            self.assertEqual("WOOL", amended["market"][2][1])
            self.assertEqual({("SELL", "MILK", 3), ("SELL", "WOOL", 3)},
                             {tuple(order) for order in amended["market"] if order[0] == "SELL"})
            self.assertEqual({"farmer", "hands", "market"}, set(amended))

    def test_committed_measurement_records_firing_and_no_confirm_outcomes(self):
        path = ROOT / "docs/measurements/SOT-2942/SOT-2945-strict-future-meta-reset.json"
        if not path.exists():
            self.skipTest("measurement not generated yet")
        report = json.loads(path.read_text())
        self.assertTrue(report["passed"])
        self.assertTrue(report["screen"]["both_seats"])
        self.assertTrue(report["screen"]["actual_firing"])
        self.assertIsNone(report["confirm"]["outcomes"])
        self.assertFalse(report["public_score_used_for_selection"])
        self.assertFalse(report["champion_hedge"]["modified"])


if __name__ == "__main__":
    unittest.main()

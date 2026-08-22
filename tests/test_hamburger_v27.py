import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/hamburger-v27/agent.py"


def load():
    spec = importlib.util.spec_from_file_location("hamburger_v27", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HamburgerV27Test(unittest.TestCase):
    def test_provenance_and_independence(self):
        source = json.loads((CANDIDATE.parent / "source.json").read_text())
        self.assertEqual("UNDECLARED", source["license"])
        self.assertIn("clean-room", source["redistribution"])
        self.assertEqual([], source["runtime_external_dependencies"])
        self.assertFalse(source["default_enabled"])
        self.assertEqual("NOT_PERFORMED", source["kaggle_submission"])
        self.assertNotIn("hamburger-v27", (ROOT / "main.py").read_text())
        self.assertEqual(64, len(hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()))

    def test_collision_order_and_terminal_relay_fire(self):
        module = load()
        tiles = [[None] * 10 for _ in range(10)]
        farm = {"money": 1000, "farmer": [4, 4], "hands": [], "tiles": tiles}
        rival = {"money": 1000, "farmer": [0, 0], "hands": [], "tiles": tiles}
        obs = {"step": 716, "player": 0, "farms": [farm, rival],
               "private": {"seeds": {}, "shed": {"WHEAT": 2, "WOOL": 1},
                           "inventories": [{"MELON": 2}]},
               "market": {"prices": {"WHEAT": 25, "WOOL": 200, "MELON": 250}}}
        action = module.agent(obs)
        self.assertIn(action["farmer"][0], {"PLACE", "DROP"})
        self.assertEqual("MELON", action["market"][0][1])
        trace = module.trace_snapshot()
        self.assertGreater(trace["collision_sell_calls"], 0)
        self.assertGreater(trace["terminal_relay_calls"], 0)

    def test_invalid_observation_is_safe(self):
        self.assertEqual({"farmer": ["PASS"], "hands": [], "market": []}, load().agent({"farms": None}))

    def test_screen_confirm_evidence(self):
        report = json.loads((ROOT / "docs/measurements/SOT-3009/hamburger-v27-screen-confirm.json").read_text())
        self.assertTrue(report["passed"])
        self.assertTrue(all(report["isolation"].values()))
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertIn(report["decision"], {"promoted-independent-hedge", "rejected-candidate-inactive", "inconclusive"})
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

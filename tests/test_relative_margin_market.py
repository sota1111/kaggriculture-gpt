import importlib.util
import json
import unittest
from pathlib import Path

from scripts.measure_relative_margin_market import ROOT, validate


def load_policy():
    path = ROOT / "candidates/relative-margin-market/policy.py"
    spec = importlib.util.spec_from_file_location("relative_margin_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RelativeMarginMarketTest(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.obs = {
            "player": 0, "step": 120, "day": 5, "hour": 0,
            "farms": [
                {"cash": 1000, "hands": [], "inventory": {"WHEAT": 3}, "tiles": [[{"kind": "PLANT", "crop": "CORN"}]]},
                {"cash": 800, "hands": [{}, {}], "tiles": [[{"kind": "PLANT", "crop": "WHEAT"}, {"kind": "PLANT", "crop": "WHEAT"}]]},
            ],
            "market": {"prices": {"WHEAT": 20, "CORN": 15}, "inventory": {"WHEAT": 100, "CORN": 9000}},
            "town": {"demand": {"WHEAT": 3}},
            "private": {"future_price": 999999, "opponent_inventory": {"WHEAT": 999}},
        }

    def test_model_uses_public_opponent_footprint_town_and_market(self):
        model = self.policy.public_opponent_model(self.obs)
        self.assertEqual(2, model["crop_footprint"]["WHEAT"])
        self.assertEqual(3, model["town_demand"]["WHEAT"])
        self.assertEqual(100, model["inventory"]["WHEAT"])
        self.assertNotIn("future_price", json.dumps(model))

    def test_joint_plan_is_bounded_and_cash_constrained(self):
        baseline = {"farmer": ["PLANT", "CORN"], "hands": [], "market": []}
        plans = self.policy.counterfactual_market_plans(self.obs, baseline)
        self.assertGreaterEqual(len(plans), 3)
        selected = self.policy.choose_relative_margin_plan(self.obs, baseline)
        self.assertLessEqual(len(selected["market"]), 10)
        bought = sum(order[2] * self.obs["market"]["prices"][order[1]]
                     for order in selected["market"] if order[0] == "BUY_PRODUCT")
        self.assertLessEqual(bought, self.obs["farms"][0]["cash"] - self.policy.MIN_CASH_RUNWAY)

    def test_holdout_and_measurement_evidence(self):
        config = json.loads((ROOT / "tests/fixtures/relative_margin_market.json").read_text())
        self.assertTrue(all(validate(config, self.policy).values()), validate(config, self.policy))
        report = json.loads((ROOT / "docs/measurements/SOT-2957/SOT-2961-relative-margin-market.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertGreater(report["windows"]["screen"]["interventions"]["total"], 0)
        self.assertIn("mean_own_reward", report["windows"]["screen"]["direct_ab"]["delta"])
        self.assertIn("mean_opponent_reward", report["windows"]["screen"]["direct_ab"]["delta"])
        self.assertFalse(report["candidate"]["default_enabled"])
        self.assertFalse(report["champion"]["modified"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

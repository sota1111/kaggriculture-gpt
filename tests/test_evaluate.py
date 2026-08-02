import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.evaluate import compare, evaluate, load_agent, run_episode
from scripts import evaluate as evaluator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/evaluation.json").read_text())


class EvaluationTest(unittest.TestCase):
    def test_fixed_seeds_are_reproducible(self):
        agent = load_agent(ROOT / "main.py")
        first = evaluate(agent, FIXTURE, FIXTURE["screen_seeds"])
        second = evaluate(agent, FIXTURE, FIXTURE["screen_seeds"])
        self.assertEqual(first, second)
        self.assertEqual(0, first["mean"]["invalid_actions"])

    def test_screen_and_confirm_use_independent_reproducible_seeds(self):
        self.assertTrue(set(FIXTURE["screen_seeds"]).isdisjoint(FIXTURE["confirm_seeds"]))
        agent = load_agent(ROOT / "main.py")
        self.assertEqual(
            evaluate(agent, FIXTURE, FIXTURE["confirm_seeds"]),
            evaluate(agent, FIXTURE, FIXTURE["confirm_seeds"]),
        )

    def test_invalid_action_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.py"
            path.write_text("def agent(obs):\n return {'farmer':['FLY'], 'hands':[], 'market':[]}\n")
            result = evaluate(load_agent(path), FIXTURE, [1])
        self.assertEqual(FIXTURE["days"] * FIXTURE["turns_per_day"], result["mean"]["invalid_actions"])
        self.assertLess(result["mean"]["leaderboard_proxy"], result["mean"]["final_assets"])

    def test_submission_contract_rejects_bad_arity_and_unknown_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad_contract.py"
            path.write_text("def agent(obs):\n return {'farmer':['PLANT','RICE'], 'hands':[], 'market':[['HIRE', 1]]}\n")
            result = run_episode(load_agent(path), FIXTURE, 1)
        self.assertGreater(result.contract_violations, 0)

    def test_threshold_rejects_regression(self):
        champion = {"mean": {"final_assets": 100, "profit": 10, "cultivated": 2, "harvested": 2, "invalid_actions": 0}}
        candidate = {"mean": {"final_assets": 99, "profit": 10, "cultivated": 2, "harvested": 2, "invalid_actions": 0}}
        passed, reasons = compare(champion, candidate, FIXTURE["thresholds"])
        self.assertFalse(passed)
        self.assertIn("final_assets ratio", reasons[0])

    def test_zero_baseline_metric_does_not_divide_by_zero(self):
        champion = {"mean": {"final_assets": 0, "profit": 0, "cultivated": 0, "harvested": 0, "invalid_actions": 0}}
        candidate = {"mean": {"final_assets": 1, "profit": 1, "cultivated": 1, "harvested": 1, "invalid_actions": 0}}
        passed, reasons = compare(champion, candidate, FIXTURE["thresholds"])
        self.assertTrue(passed, reasons)

    def test_multi_worker_candidate_routes_without_invalid_actions(self):
        agent = load_agent(ROOT / "main.py")
        agent.HIRE_TARGET = 3
        result = run_episode(agent, FIXTURE, 11)
        self.assertEqual(0, result.invalid_actions)
        self.assertGreater(result.cultivated, 1)
        self.assertGreater(result.harvested, 1)

    def test_worker_assignments_are_unique_and_respect_seed_count(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0,
            "day": 0,
            "hour": 3,
            "farms": [{
                "money": 100,
                "farmer": [0, 0],
                "hands": [[1, 0], [2, 0]],
                "hires_today": 2,
                "tiles": [[None, None, None], [None, None, None], [None, None, None]],
            }],
            "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[], [], []]},
        }
        result = agent.agent(obs)
        plant_actions = [action for action in [result["farmer"], *result["hands"]] if action[0] == "PLANT"]
        self.assertEqual(1, len(plant_actions))

    def test_movement_stays_within_board_at_boundary(self):
        agent = load_agent(ROOT / "main.py")
        tiles = [["LOCKED" for _ in range(3)] for _ in range(3)]
        tiles[0][0] = None
        obs = {
            "player": 0, "day": 0,
            "farms": [{"money": 100, "farmer": [2, 2], "hands": [], "hires_today": 0, "tiles": tiles}],
            "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[]]},
        }
        self.assertIn(agent.agent(obs)["farmer"][0], {"NORTH", "WEST"})

    def test_missing_market_keys_and_unknown_inventory_are_safe(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 1,
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
            "private": {"shed": {"UNKNOWN": 3}, "seeds": {}, "inventories": [[]]},
        }
        result = agent.agent(obs)
        self.assertEqual({"farmer", "hands", "market"}, set(result))
        self.assertLessEqual(len(result["market"]), 10)
        self.assertNotIn("UNKNOWN", [action[1] for action in result["market"] if len(action) > 1])

    def test_cash_reserve_and_market_order_cap_are_preserved(self):
        agent = load_agent(ROOT / "main.py")
        crops = {f"CROP{i}": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3,
                              "fallback_price": 20, "sell_above": 10} for i in range(12)}
        obs = {
            "player": 0, "day": 2, "crops": crops,
            "market": {"prices": {crop: 20 for crop in crops}},
            "farms": [{"money": 109, "farmer": [0, 0], "hands": [], "hires_today": 0, "tiles": [["LOCKED"]]}],
            "private": {"shed": {crop: 1 for crop in crops}, "seeds": {}, "inventories": [[]]},
        }
        result = agent.agent(obs)
        self.assertLessEqual(len(result["market"]), 10)
        self.assertFalse(any(action[0] in {"BUY_SEED", "HIRE"} for action in result["market"]))

    def test_price_aware_strategy_holds_inventory_below_target(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 3,
            "crops": {"CORN": {"seed_price": 18, "maturity_days": 3, "expected_yield": 4,
                                  "fallback_price": 14, "sell_above": 17}},
            "market": {"prices": {"CORN": 12}},
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [["LOCKED"]]}],
            "private": {"shed": {"CORN": 5}, "seeds": {}, "inventories": [[]]},
        }
        self.assertFalse(any(action[0] == "SELL" for action in agent.agent(obs)["market"]))

    def test_report_maps_champion_candidate_and_submission_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            argv = ["evaluate.py", "--champion", str(ROOT / "tests/fixtures/champion_sot_2263.py"),
                    "--candidate", str(ROOT / "main.py"), "--fixture",
                    str(ROOT / "tests/fixtures/evaluation.json"), "--output", str(output)]
            with mock.patch("sys.argv", argv):
                self.assertEqual(0, evaluator.main())
            report = json.loads(output.read_text())
        self.assertEqual(str(ROOT / "main.py"), report["provenance"]["candidate"])
        self.assertEqual("submission.tar.gz", report["provenance"]["submission_artifact"])
        self.assertEqual(2, report["oracle"]["version"])
        self.assertEqual(10, report["submission_contract"]["max_market_orders"])


if __name__ == "__main__":
    unittest.main()

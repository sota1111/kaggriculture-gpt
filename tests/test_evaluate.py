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

    def test_global_assignment_does_not_let_planting_delay_harvest(self):
        agent = load_agent(ROOT / "main.py")
        tiles = [["LOCKED"] * 5 for _ in range(2)]
        tiles[0][1] = None
        tiles[0][3] = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
                       "watered_today": True, "yield_units": 3}
        obs = {"player": 0, "day": 3, "hour": 10,
               "farms": [{"money": 100, "farmer": [0, 0], "hands": [[4, 0]], "tiles": tiles}],
               "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[], []]}}
        result = agent.agent(obs)
        self.assertEqual(["EAST"], result["farmer"])
        self.assertEqual([["WEST"]], result["hands"])

    def test_global_assignment_avoids_duplicate_move_destinations(self):
        agent = load_agent(ROOT / "main.py")
        tiles = [["LOCKED"] * 3 for _ in range(3)]
        tiles[1][1] = {"kind": "WEED"}
        tiles[1][2] = {"kind": "WEED"}
        obs = {"player": 0, "day": 1, "hour": 2,
               "farms": [{"money": 100, "farmer": [0, 0], "hands": [[2, 0]], "tiles": tiles}],
               "private": {"shed": {}, "seeds": {}, "inventories": [[], []]}}
        result = agent.agent(obs)
        actions = [result["farmer"], *result["hands"]]
        offsets = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
        destinations = [(x + offsets[action[0]][0], y + offsets[action[0]][1])
                        for (x, y), action in zip(((0, 0), (2, 0)), actions)]
        self.assertEqual(len(destinations), len(set(destinations)))

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

    def test_finite_horizon_prefers_crop_with_more_realizable_profit(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 8, "total_days": 12,
            "crops": {
                "FAST": {"seed_price": 10, "maturity_days": 1, "expected_yield": 2,
                         "fallback_price": 12, "price_forecast": [12] * 12},
                "SLOW": {"seed_price": 10, "maturity_days": 4, "expected_yield": 10,
                         "fallback_price": 20, "price_forecast": [20] * 12},
            },
            "market": {"prices": {"FAST": 12, "SLOW": 20}},
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
            "private": {"shed": {}, "seeds": {"FAST": 1, "SLOW": 1}, "inventories": [[]]},
        }
        crop, _ = agent._choose_crop(obs, obs["private"]["seeds"])
        self.assertEqual("FAST", crop)

    def test_finite_horizon_waits_for_forecast_peak_and_sells_on_final_day(self):
        agent = load_agent(ROOT / "main.py")
        base = {
            "player": 0, "total_days": 3,
            "crops": {"WHEAT": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3,
                                    "fallback_price": 10, "sell_above": 10,
                                    "price_forecast": [10, 20, 15]}},
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [["LOCKED"]]}],
            "private": {"shed": {"WHEAT": 2}, "seeds": {}, "inventories": [[]]},
        }
        day_zero = dict(base, day=0, market={"prices": {"WHEAT": 10}})
        self.assertFalse(any(order[0] == "SELL" for order in agent.agent(day_zero)["market"]))
        final_day = dict(base, day=2, market={"prices": {"WHEAT": 15}})
        self.assertTrue(any(order[0] == "SELL" for order in agent.agent(final_day)["market"]))

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

import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate import compare, evaluate, load_agent, run_episode


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/evaluation.json").read_text())


class EvaluationTest(unittest.TestCase):
    def test_fixed_seeds_are_reproducible(self):
        agent = load_agent(ROOT / "main.py")
        first = evaluate(agent, FIXTURE, FIXTURE["screen_seeds"])
        second = evaluate(agent, FIXTURE, FIXTURE["screen_seeds"])
        self.assertEqual(first, second)
        self.assertEqual(0, first["mean"]["invalid_actions"])

    def test_invalid_action_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.py"
            path.write_text("def agent(obs):\n return {'farmer':['FLY'], 'hands':[], 'market':[]}\n")
            result = evaluate(load_agent(path), FIXTURE, [1])
        self.assertEqual(FIXTURE["days"] * FIXTURE["turns_per_day"], result["mean"]["invalid_actions"])

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


if __name__ == "__main__":
    unittest.main()

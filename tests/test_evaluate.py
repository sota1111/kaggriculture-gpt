import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate import compare, evaluate, load_agent


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
        self.assertEqual(FIXTURE["days"], result["mean"]["invalid_actions"])

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


if __name__ == "__main__":
    unittest.main()

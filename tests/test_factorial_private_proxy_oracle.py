import json
import unittest
from pathlib import Path

from scripts.measure_factorial_private_proxy_oracle import build_panel, factorial_effects, validate_manifest


ROOT = Path(__file__).resolve().parents[1]


class FactorialPrivateProxyOracleTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "tests/fixtures/factorial_private_proxy_oracle.json").read_text())

    def test_manifest_is_balanced_sealed_and_leak_free(self):
        validation = validate_manifest(self.manifest)
        self.assertTrue(validation["passed"], validation["checks"])
        self.assertEqual(16, len(validation["panels"]["screen"]))
        self.assertEqual(16, len(validation["panels"]["confirm"]))

    def test_both_seats_are_directly_compared_at_same_seed(self):
        panel = build_panel(self.manifest, "screen")
        for episode in {row["episode"] for row in panel}:
            rows = [row for row in panel if row["episode"] == episode]
            self.assertEqual({0, 1}, {row["seat"] for row in rows})
            self.assertEqual(1, len({row["seed"] for row in rows}))

    def test_factorial_main_and_interaction_effects(self):
        rows = []
        for market in ("low", "high"):
            for opponent in ("low", "high"):
                for seat in ("low", "high"):
                    for time in ("low", "high"):
                        margin = (10 if market == "high" else 0) + (4 if opponent == seat else 0)
                        rows.append({"market": market, "opponent_level": opponent, "seat_level": seat,
                                     "time": time, "margin": margin, "candidate_rank": 1,
                                     "tail_score": margin})
        effects = factorial_effects(rows)
        self.assertEqual(10, effects["market"]["margin"])
        self.assertEqual(4, effects["opponent*seat"]["margin"])
        self.assertEqual(0, effects["time"]["margin"])


if __name__ == "__main__":
    unittest.main()

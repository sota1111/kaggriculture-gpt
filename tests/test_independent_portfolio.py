import json
import tempfile
import unittest
from pathlib import Path

from scripts.measure_independent_portfolio import ROOT, _flagged_candidate, _paired
from scripts.measure_private_proxy_oracle import validate_split


class IndependentPortfolioTest(unittest.TestCase):
    def test_registered_split_is_nonoverlapping_and_both_seat(self):
        manifest = json.loads((ROOT / "tests/fixtures/private_proxy_oracle.json").read_text())
        result = validate_split(manifest)
        self.assertTrue(result["passed"])
        self.assertEqual({"lineage": [], "episode": [], "seed": [], "time_slice": []},
                         result["overlap"])

    def test_pairing_is_same_seed_seat_and_opponent(self):
        control = [{"seed": 1, "seat": 0, "opponent": "x", "margin": -4,
                    "candidate_rank": 2, "terminal_statuses": ["DONE", "DONE"]}]
        candidate = [{**control[0], "margin": 3, "candidate_rank": 1}]
        result = _paired(candidate, control)
        self.assertEqual(7, result["summary"]["mean_margin_delta"])
        self.assertEqual(1, result["summary"]["candidate_mean_rank"])

    def test_ephemeral_fertilizer_candidate_does_not_modify_champion(self):
        source = ROOT / "main.py"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            candidate = _flagged_candidate(source, Path(directory) / "candidate.py")
            self.assertIn("FERTILIZER_CONSTRAINED_PRODUCTION = True", candidate.read_text())
        self.assertEqual(before, source.read_bytes())


if __name__ == "__main__":
    unittest.main()

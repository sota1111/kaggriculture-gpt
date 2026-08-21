import json
import unittest

from scripts.measure_sealed_direction_tournament import ROOT, _delta, _passes, decide


class SealedDirectionTournamentTest(unittest.TestCase):
    def test_pessimistic_tail_blocks_mean_only_uplift(self):
        delta = {"mean_margin": 10, "p20_margin": -1, "worst_margin": -1, "mean_rank": 0}
        self.assertFalse(_passes(delta))
        self.assertFalse(_passes(delta, confirm=True))

    def test_exact_same_identity_summary_delta(self):
        champion = {"mean_margin": -10, "p20_margin": -20, "worst_margin": -30, "mean_rank": 2}
        candidate = {"mean_margin": 5, "p20_margin": -5, "worst_margin": -10, "mean_rank": 1}
        self.assertEqual({"mean_margin": 15, "p20_margin": 15, "worst_margin": 20, "mean_rank": -1}, _delta(candidate, champion))

    def test_real_manifest_is_frozen_and_fail_closed(self):
        manifest = json.loads((ROOT / "tests/fixtures/sealed_direction_tournament.json").read_text())
        report = decide(manifest)
        self.assertTrue(report["passed"])
        self.assertTrue(report["champion"]["retained"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])
        self.assertFalse(report["public_score_used_for_selection"])
        self.assertTrue(all(row["real_firing"] for row in report["candidates"].values()))

        manifest["candidate_hashes"]["champion"] = "0" * 64
        self.assertFalse(decide(manifest)["passed"])


if __name__ == "__main__":
    unittest.main()

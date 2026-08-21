import unittest

from scripts.measure_sealed_private_proxy_portfolio import decide, pair, screen_passes


class SealedPrivateProxyPortfolioTest(unittest.TestCase):
    def test_pair_requires_exact_registered_identity(self):
        base = {"market_regime": "m", "opponent": "o", "episode": "e", "seed": 1,
                "seat": 0, "time_slice": "t", "margin": -5, "candidate_rank": 2,
                "terminal_statuses": ["DONE", "DONE"]}
        result = pair([{**base, "margin": 3, "candidate_rank": 1}], [base])
        self.assertEqual(8, result["summary"]["mean_margin_delta"])
        self.assertTrue(screen_passes(result["summary"]))

    def test_tail_regression_blocks_screen(self):
        summary = {"candidate_mean_rank": 1, "champion_mean_rank": 2,
                   "mean_margin_delta": 10, "worst_margin_delta": -1}
        self.assertFalse(screen_passes(summary))

    def test_rejection_requires_confirm_and_firing(self):
        screen = {"summary": {"candidate_mean_rank": 1, "champion_mean_rank": 2,
                              "mean_margin_delta": 1, "worst_margin_delta": 0}}
        confirm = {"summary": {"candidate_mean_rank": 2, "champion_mean_rank": 2,
                               "mean_margin_delta": -1, "worst_margin_delta": -1}}
        self.assertEqual("rejected", decide(screen, confirm, True)[0])
        self.assertEqual("inconclusive", decide(screen, confirm, False)[0])


if __name__ == "__main__":
    unittest.main()

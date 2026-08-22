import copy
import json
import unittest

from scripts.measure_adaptive_replay_portfolio import FIXTURE, ROOT, validate


class AdaptiveReplayPortfolioTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(FIXTURE.read_text())
        self.reports = {name: json.loads((ROOT / path).read_text())
                        for name, path in self.manifest["screen_reports"].items()}

    def test_all_leakage_axes_are_disjoint_and_both_seats_are_present(self):
        result = validate(self.manifest, self.reports)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(not values for values in result["screen_confirm_overlap"].values()))

    def test_each_leakage_axis_fails_closed(self):
        screen_row = self.reports["v111"]["screen"]["candidate_rows"][0]
        for axis in ("opponent", "lineage", "episode", "seed", "seat_group", "time_slice"):
            broken = copy.deepcopy(self.manifest)
            broken["sealed_confirm"][0][axis] = screen_row.get(axis)
            self.assertFalse(validate(broken, self.reports)["passed"], axis)

    def test_committed_measurement_freezes_all_agents_and_reports_robust_metrics(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2981/SOT-2984-adaptive-replay-portfolio.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual({"v111_economic_core", "r5a_recovery", "conditional_memory", "old_champion"},
                         set(report["frozen_artifacts"]))
        for candidate in report["sealed_tournament"].values():
            summary = candidate["summary"]
            self.assertTrue(summary["all_done"])
            self.assertTrue({"pessimistic_p20_margin", "rank_stability_stdev", "matchup_spread"} <= set(summary))
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])
        self.assertTrue(report["champion_hedge_retained"])
        self.assertEqual("conditional_memory", report["portfolio_selection"]["selected_candidate"])
        self.assertTrue(report["portfolio_selection"]["old_champion_retained_as_hedge"])


if __name__ == "__main__":
    unittest.main()

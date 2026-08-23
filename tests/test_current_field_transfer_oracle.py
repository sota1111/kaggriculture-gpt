import copy
import json
import unittest
from pathlib import Path

from scripts.measure_current_field_transfer_oracle import (
    build_chronological_cohort, measure, validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


class CurrentFieldTransferOracleTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "tests/fixtures/current_field_transfer_manifest.json").read_text())

    def test_provenance_chronology_and_leakage_checks_pass(self):
        result = validate_manifest(self.manifest)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(not values for values in result["overlap"].values()))

    def test_builder_sorts_before_the_frozen_split(self):
        rows = list(reversed(self.manifest["cohort"]["records"]))
        windows = build_chronological_cohort(rows, 3)
        self.assertLess(windows["screen"][-1]["observed_at"], windows["confirm"][0]["observed_at"])

    def test_identity_seat_time_and_payload_leaks_fail_closed(self):
        for field in ("opponent_id", "lineage_id", "episode_id", "seed", "time_cohort"):
            broken = copy.deepcopy(self.manifest)
            broken["cohort"]["records"][3][field] = broken["cohort"]["records"][0][field]
            self.assertFalse(validate_manifest(broken)["passed"], field)
        broken = copy.deepcopy(self.manifest)
        del broken["cohort"]["records"][0]["results"]["C95"]["seat_margins"]["1"]
        self.assertFalse(validate_manifest(broken)["checks"]["all_targets_same_seed_both_seats"])
        broken = copy.deepcopy(self.manifest)
        broken["cohort"]["records"][0]["replay_bytes"] = "forbidden"
        self.assertFalse(validate_manifest(broken)["checks"]["metadata_only"])

    def test_confirm_is_not_a_selection_input_and_drift_is_reported(self):
        report = measure(self.manifest)
        self.assertTrue(report["passed"], report)
        self.assertEqual("C95", report["screen_selected"])
        self.assertEqual("incumbent", report["confirm_best"])
        self.assertFalse(report["confirm_used_for_selection"])
        self.assertFalse(report["ranking_stable"])
        self.assertEqual("rejected", report["oracle_decision"])
        self.assertIn("p20_pair_margin", report["drift"]["C95"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

import copy
import json
import unittest
from pathlib import Path

from scripts.measure_live_meta_transfer_oracle import measure, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


class LiveMetaTransferOracleTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "tests/fixtures/live_meta_transfer_oracle.json").read_text())

    def test_manifest_is_provenance_complete_and_split_clean(self):
        result = validate_manifest(self.manifest)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(not values for values in result["overlap"].values()))

    def test_identity_overlap_and_missing_seat_fail_closed(self):
        for field in ("lineage_prefix", "episode", "seed", "time_cohort"):
            broken = copy.deepcopy(self.manifest)
            broken["panels"]["confirm"][0][field] = broken["panels"]["screen"][0][field]
            self.assertFalse(validate_manifest(broken)["passed"], field)
        broken = copy.deepcopy(self.manifest)
        broken["panels"]["confirm"][1]["seat"] = 0
        self.assertFalse(validate_manifest(broken)["passed"])

    def test_private_future_fields_and_hash_drift_fail_closed(self):
        broken = copy.deepcopy(self.manifest)
        broken["panels"]["screen"][0]["private_reward"] = 1
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["sources"][0]["sha256"] = "bad"
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["evaluation_targets"][0]["sha256"] = "0" * 64
        self.assertFalse(validate_manifest(broken)["passed"])

    def test_measurement_keeps_oracle_and_agent_decisions_separate(self):
        result = measure(self.manifest)
        self.assertTrue(result["passed"])
        self.assertEqual("promoted", result["oracle_decision"])
        self.assertEqual("NOT_EVALUATED", result["agent_decision"])
        self.assertEqual({"current-champion", "independent-candidate"},
                         {row["role"] for row in result["evaluation_targets"]})
        self.assertIn("p20_margin", result["transfer_drift"]["confirm_minus_screen"])
        self.assertIn("opponent_time_market_interaction", result["windows"]["confirm"])
        self.assertEqual(0, result["bias_and_dependence"]["validation_self_play_rows"])


if __name__ == "__main__":
    unittest.main()

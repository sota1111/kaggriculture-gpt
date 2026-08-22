import copy
import json
import unittest
from pathlib import Path

from scripts.measure_strict_future_live_field_oracle import measure, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


class StrictFutureLiveFieldOracleTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "tests/fixtures/strict_future_live_field_oracle.json").read_text())

    def test_provenance_split_cutoff_and_digest_are_valid(self):
        result = validate_manifest(self.manifest)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(not overlap for overlap in result["overlap"].values()))

    def test_each_split_axis_and_confirm_chronology_fail_closed(self):
        for field in ("opponent", "lineage", "episode", "seed", "time_slice", "market_regime"):
            broken = copy.deepcopy(self.manifest)
            broken["panels"]["confirm"][0][field] = broken["panels"]["screen"][0][field]
            self.assertFalse(validate_manifest(broken)["passed"], field)
        broken = copy.deepcopy(self.manifest)
        broken["panels"]["confirm"][0]["time_index"] = 0
        self.assertFalse(validate_manifest(broken)["passed"])

    def test_both_seats_hashes_and_snapshot_digest_fail_closed(self):
        broken = copy.deepcopy(self.manifest)
        broken["panels"]["confirm"][1]["seat"] = 0
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["foundations"][0]["sha256"] = "0" * 64
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["acquisition"]["immutable_snapshot_sha256"] = "0" * 64
        self.assertFalse(validate_manifest(broken)["passed"])

    def test_deterministic_metrics_and_inconclusive_fallback(self):
        first = measure(self.manifest)
        second = measure(copy.deepcopy(self.manifest))
        self.assertEqual(first, second)
        self.assertTrue(first["passed"])
        self.assertEqual("inconclusive", first["oracle_decision"])
        self.assertEqual("NOT_EVALUATED_OR_PROMOTED", first["agent_decision"])
        for window in ("screen", "confirm"):
            self.assertEqual(4, len(first["windows"][window]))
            for summary in first["windows"][window].values():
                self.assertEqual(4, summary["episodes"])
                self.assertEqual(4, sum(summary["wlt"].values()))
                self.assertIn("seat_symmetry_gap", summary)


if __name__ == "__main__":
    unittest.main()

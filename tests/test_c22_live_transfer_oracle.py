import copy
import json
import unittest
from pathlib import Path

from scripts.measure_c22_live_transfer_oracle import validate_manifest

ROOT = Path(__file__).resolve().parents[1]


class C22LiveTransferOracleTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "tests/fixtures/c22_live_transfer_oracle.json").read_text())

    def test_provenance_boundaries_and_blind_anchors_are_pinned(self):
        result = validate_manifest(self.manifest)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(not values for values in result["overlap"].values()))

    def test_every_split_dimension_fails_closed_on_overlap(self):
        for field in ("opponent", "lineage", "episode", "seed", "time_slice", "market_regime"):
            broken = copy.deepcopy(self.manifest)
            broken["panels"]["confirm"][0][field] = broken["panels"]["screen"][0][field]
            self.assertFalse(validate_manifest(broken)["passed"], field)

    def test_hash_drift_private_future_and_replay_fields_fail_closed(self):
        broken = copy.deepcopy(self.manifest)
        broken["sources"][0]["sha256"] = "bad"
        self.assertFalse(validate_manifest(broken)["passed"])
        for field in ("private_reward", "future_outcome", "replay_json"):
            broken = copy.deepcopy(self.manifest)
            broken["panels"]["screen"][0][field] = "forbidden"
            self.assertFalse(validate_manifest(broken)["passed"], field)

    def test_missing_seat_and_anchor_hash_drift_fail_closed(self):
        broken = copy.deepcopy(self.manifest)
        broken["panels"]["confirm"][1]["seat"] = 0
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["public_blind_anchors"][0]["sha256"] = "0" * 64
        self.assertFalse(validate_manifest(broken)["passed"])


if __name__ == "__main__":
    unittest.main()

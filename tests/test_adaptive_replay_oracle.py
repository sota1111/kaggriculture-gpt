import copy
import json
import unittest
from pathlib import Path

from scripts.measure_adaptive_replay_oracle import canonical_sha256, measure, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


class AdaptiveReplayOracleTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "tests/fixtures/adaptive_replay_oracle.json").read_text())

    def test_manifest_and_every_split_axis_are_leak_free(self):
        result = validate_manifest(self.manifest)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(not values for pairs in result["overlaps"].values() for values in pairs.values()))

    def test_every_isolation_axis_fails_closed_on_overlap(self):
        for axis in ("opponent_lineage", "episode_id", "seed", "seat_group", "time_slice", "market_regime"):
            broken = copy.deepcopy(self.manifest)
            broken["records"][4][axis] = broken["records"][0][axis]
            if axis in {"opponent_lineage", "episode_id", "seed", "time_slice", "market_regime"}:
                identity = {key: broken["records"][4][key] for key in
                            ("opponent_lineage", "episode_id", "seed", "seat", "time_slice", "market_regime")}
                broken["records"][4]["identity_hash"] = canonical_sha256(identity)
            self.assertFalse(validate_manifest(broken)["passed"], axis)

    def test_hash_drift_credentials_and_raw_bytes_fail_closed(self):
        broken = copy.deepcopy(self.manifest)
        broken["records"][0]["identity_hash"] = "0" * 64
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["sources"][0]["credential_token"] = "never"
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["sources"][0]["raw_boundary"] = "committed"
        self.assertFalse(validate_manifest(broken)["passed"])

    def test_open_loop_is_stress_only(self):
        result = measure(self.manifest)
        self.assertTrue(result["passed"])
        self.assertIsNone(result["splits"]["public"]["open_loop_stress"]["mean_margin"])
        broken = copy.deepcopy(self.manifest)
        stress = next(row for row in broken["records"] if row["execution_mode"] == "open-loop-stress")
        stress["closed_loop_win_probability"] = 0.5
        self.assertFalse(validate_manifest(broken)["passed"])

    def test_transfer_trust_is_deterministic_and_reports_required_metrics(self):
        first = measure(self.manifest)
        second = measure(self.manifest)
        self.assertEqual(canonical_sha256(first), canonical_sha256(second))
        for target in ("public", "live"):
            self.assertIn("score_0_to_1", first["transfer_trust"][target])
            gap = first["transfer_trust"][target]["vs_local_gap"]
            self.assertTrue({"mean_rank", "mean_margin", "p20_margin", "worst_margin",
                             "closed_loop_win_probability"} <= set(gap))
        self.assertEqual("NOT_EVALUATED", first["agent_decision"])


if __name__ == "__main__":
    unittest.main()

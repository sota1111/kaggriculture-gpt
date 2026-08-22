import copy
import json
import unittest
from pathlib import Path

from scripts.measure_distribution_robust_oracle import (
    distribution_summary,
    transfer_trust,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


class DistributionRobustOracleTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (ROOT / "tests/fixtures/distribution_robust_oracle.json").read_text()
        )

    def test_manifest_is_hash_pinned_and_leak_free(self):
        validation = validate_manifest(self.manifest)
        self.assertTrue(validation["passed"], validation)
        self.assertTrue(all(not values for values in validation["overlap"].values()))

    def test_each_leak_dimension_fails_closed(self):
        for field in ("opponent", "lineage", "episode", "seed", "time_slice"):
            broken = copy.deepcopy(self.manifest)
            broken["panels"]["confirm"][0][field] = broken["panels"]["screen"][0][field]
            self.assertFalse(validate_manifest(broken)["passed"], field)
        broken = copy.deepcopy(self.manifest)
        broken["panels"]["confirm"][1]["seat"] = 0
        self.assertFalse(validate_manifest(broken)["passed"])
        broken = copy.deepcopy(self.manifest)
        broken["open_loop_reference"]["source_sha256"] = "0" * 64
        self.assertFalse(validate_manifest(broken)["passed"])

    def test_cluster_balancing_prevents_large_cluster_dominance(self):
        rows = [
            {"cluster":"large","market_regime":"normal","margin":100,"candidate_rank":1},
            {"cluster":"large","market_regime":"normal","margin":100,"candidate_rank":1},
            {"cluster":"large","market_regime":"normal","margin":100,"candidate_rank":1},
            {"cluster":"small","market_regime":"stress","margin":-100,"candidate_rank":2},
        ]
        result = distribution_summary(rows)
        self.assertEqual(50, result["overall"]["mean_margin"])
        self.assertEqual(0, result["cluster_balanced"]["mean_margin"])
        self.assertEqual(-100, result["cluster_balanced"]["worst_margin"])

    def test_transfer_trust_keeps_open_and_closed_loop_separate(self):
        rows = [{"cluster":"a","market_regime":"r","margin":10,"candidate_rank":1}]
        screen = distribution_summary(rows)
        confirm = distribution_summary([{**rows[0], "margin":5}])
        reference = {"metrics":{"mean_rank":0,"mean_margin":2,"p20_margin":2,"worst_margin":2}}
        trust = transfer_trust(screen, confirm, reference)
        self.assertEqual(-5, trust["closed_loop_confirm_minus_screen"]["mean_margin"])
        self.assertEqual(-7, trust["closed_minus_open_disagreement"]["mean_margin"])


if __name__ == "__main__":
    unittest.main()

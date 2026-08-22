import json
import unittest

from scripts.measure_harvestforge_x import ROOT, validate_manifest


class HarvestForgeXTest(unittest.TestCase):
    def test_fail_closed_provenance_and_holdout_manifest(self):
        fixture = json.loads((ROOT / "tests/fixtures/harvestforge_x.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate_manifest(fixture, source).values()), validate_manifest(fixture, source))

    def test_measurement_records_contract_gate_and_independence(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2962/SOT-2963-harvestforge-x.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertTrue(report["action_family_fingerprint"]["diverged_from_champion"])
        self.assertEqual({0, 1}, {r["seat"] for r in report["screen"]["candidate_rows"]})
        self.assertEqual("UNSPECIFIED", report["source"]["license"])
        self.assertEqual("prohibited-fail-closed", report["source"]["redistribution"])
        self.assertFalse(report["champion"]["modified"])
        self.assertFalse(report["public_score_used_for_promotion"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

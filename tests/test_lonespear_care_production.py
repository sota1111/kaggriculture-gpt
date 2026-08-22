import json
import unittest
from pathlib import Path

from scripts.measure_lonespear_care_production import ROOT, validate


class LonespearCareProductionTest(unittest.TestCase):
    def test_provenance_portability_and_holdout_manifest(self):
        fixture = json.loads((ROOT / "tests/fixtures/lonespear_care_production.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate(fixture, source).values()), validate(fixture, source))

    def test_measurement_records_real_contract_and_divergence(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2957/SOT-2959-lonespear-care-production.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertTrue(report["action_family_fingerprint"]["diverged_from_champion"])
        self.assertEqual({0, 1}, {row["seat"] for row in report["screen"]["candidate_rows"]})
        if not report["confirm"].get("skipped"):
            self.assertEqual({0, 1}, {row["seat"] for row in report["confirm"]["candidate_rows"]})
        self.assertIn("gate", report["screen"])
        self.assertIn("mean_margin", report["screen"]["gate"]["deltas"])
        self.assertFalse(report["default_enabled"])
        self.assertFalse(report["champion"]["modified"])
        self.assertFalse(report["public_score_used_for_promotion"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])
        self.assertTrue(report["coherent_intervention"]["exact_whole_agent"])
        self.assertFalse(report["coherent_intervention"]["individual_rejected_axes_retried"])


if __name__ == "__main__":
    unittest.main()

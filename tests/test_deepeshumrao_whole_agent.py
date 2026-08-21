import json
import unittest
from pathlib import Path

from scripts.measure_deepeshumrao_whole_agent import ROOT, validate


class LicensedWholeAgentTest(unittest.TestCase):
    def test_provenance_portability_and_holdout_manifest(self):
        fixture = json.loads((ROOT / "tests/fixtures/deepeshumrao_whole_agent.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate(fixture, source).values()), validate(fixture, source))

    def test_measurement_records_real_contract_and_divergence(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2948/SOT-2951-licensed-whole-agent.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertTrue(report["action_family_fingerprint"]["diverged_from_champion"])
        self.assertEqual({0, 1}, {row["seat"] for row in report["screen"]["rows"]})
        self.assertEqual({0, 1}, {row["seat"] for row in report["confirm"]["rows"]})
        self.assertFalse(report["default_enabled"])
        self.assertFalse(report["champion"]["modified"])
        self.assertFalse(report["public_score_used_for_promotion"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

import json
import unittest

from scripts.measure_apache_agent_builder import ROOT, validate


class ApacheAgentBuilderTest(unittest.TestCase):
    def test_provenance_portability_and_holdout_manifest(self):
        fixture = json.loads((ROOT / "tests/fixtures/apache_agent_builder.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate(fixture, source).values()), validate(fixture, source))

    def test_measurement_records_contract_and_governed_decision(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2987/SOT-2987-apache-agent-builder.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertEqual("PASS", report["invalid_observation_contract"])
        self.assertTrue(report["action_family_fingerprint"]["diverged_from_champion"])
        self.assertEqual({0, 1}, {row["seat"] for row in report["screen"]["candidate_rows"]})
        self.assertIn(report["decision"], {"promoted-independent-hedge", "rejected-candidate-inactive"})
        self.assertFalse(report["default_enabled"])
        self.assertFalse(report["champion"]["modified"])
        self.assertFalse(report["public_score_used_for_promotion"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

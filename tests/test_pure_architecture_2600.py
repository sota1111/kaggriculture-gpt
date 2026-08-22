import json
import unittest

from scripts.measure_pure_architecture_2600 import ROOT, validate_manifest


class PureArchitecture2600Test(unittest.TestCase):
    def test_fail_closed_provenance_and_independent_fixture(self):
        fixture = json.loads((ROOT / "tests/fixtures/pure_architecture_2600.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate_manifest(fixture, source).values()), validate_manifest(fixture, source))

    def test_measurement_records_contract_tail_and_hedge(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2962/SOT-2965-pure-architecture-2600.json").read_text())
        self.assertTrue(report["passed"])
        self.assertTrue(report["runtime_contract"]["passed"])
        self.assertTrue(report["action_family_fingerprint"]["diverged_from_champion"])
        self.assertEqual({0, 1}, {row["seat"] for row in report["screen"]["candidate_rows"]})
        self.assertIn("p20_margin", report["screen"]["candidate"])
        self.assertEqual("UNSPECIFIED", report["source"]["license"])
        self.assertEqual("prohibited-fail-closed", report["source"]["redistribution"])
        self.assertFalse(report["acquisition"]["redistributed"])
        self.assertFalse(report["champion"]["modified"])
        self.assertFalse(report["public_score_used_for_promotion"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])
        self.assertEqual("promoted", report["performance_decision"])
        self.assertEqual("rejected", report["decision"])


if __name__ == "__main__":
    unittest.main()

import json, unittest
from scripts.measure_kaito_v27_strict_future import ROOT, validate_manifest

class KaitoV27StrictFutureTest(unittest.TestCase):
    def test_fail_closed_provenance_and_chronology(self):
        fixture = json.loads((ROOT / "tests/fixtures/kaito_v27_strict_future.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate_manifest(fixture, source).values()), validate_manifest(fixture, source))

    def test_saved_evidence(self):
        report = json.loads((ROOT / "docs/measurements/SOT-3003/v27-strict-future-screen-confirm.json").read_text())
        self.assertEqual(report["screen_gate"], "PASS")
        self.assertTrue(report["runtime_contract_passed"])
        self.assertEqual(report["decision"], "inconclusive")
        self.assertTrue(report["route_identity"]["single_route_both_seats"])
        self.assertTrue(report["route_identity"]["distinct_from_v19_sha256"])
        self.assertTrue(report["route_identity"]["distinct_from_v39_sha256"])
        self.assertEqual(report["source"]["redistribution"], "prohibited-fail-closed")
        self.assertEqual(report["kaggle_submission"], "NOT_PERFORMED")
        for cohort in ("screen", "confirm"):
            self.assertTrue(report[cohort]["summary"]["all_done"])
            self.assertEqual(report[cohort]["summary"]["invalid_actions"], 0)
            self.assertGreater(report[cohort]["summary"]["actor_firings"], 0)
            self.assertGreater(report[cohort]["summary"]["market_firings"], 0)
            self.assertGreater(report[cohort]["summary"]["sell_slot_firings"], 0)

if __name__ == "__main__": unittest.main()

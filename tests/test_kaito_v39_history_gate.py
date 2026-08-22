import json
import unittest

from scripts.measure_kaito_v39_history_gate import ROOT, validate_manifest


class KaitoV39HistoryGateTest(unittest.TestCase):
    def test_fail_closed_provenance_and_lineage_manifest(self):
        fixture = json.loads((ROOT / "tests/fixtures/kaito_v39_history_gate.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        self.assertTrue(all(validate_manifest(fixture, source).values()), validate_manifest(fixture, source))

    def test_measurement_records_router_contract_and_sealed_discipline(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2962/SOT-2966-kaito-v39-history-gate.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertTrue(report["router_audit"]["public_state_only"])
        self.assertTrue(report["router_audit"]["private_future_metadata_mutation_invariant"])
        self.assertTrue(report["router_audit"]["unknown_state"]["abstained_to_conservative_fallback"])
        self.assertTrue(report["history_gate_evidence"]["fired"])
        self.assertTrue(report["history_gate_evidence"]["action_divergence_measured"])
        self.assertEqual([96, 120, 122, 132, 144], report["router_audit"]["checkpoints"])
        self.assertEqual(report["screen"]["gate"]["passed"], report["confirm"].get("consumed", False))
        self.assertFalse(report["champion"]["modified"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

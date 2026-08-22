import hashlib, json, unittest
from pathlib import Path
from scripts.measure_structured_economic_policy import ADAPTER, OUTPUT, SOURCE

ROOT=Path(__file__).resolve().parents[1]
class StructuredEconomicPolicyTest(unittest.TestCase):
    def test_provenance_is_pinned_and_fail_closed(self):
        source=json.loads(SOURCE.read_text())
        self.assertEqual(source["notebook_sha256"],"2968c446a3c978a0680f99f67b9f0fcb64e1343b9b703d29a41cdc88514ac981")
        self.assertEqual(source["acquired_content_fingerprint_sha256"],"6c0f2671123e9b5f0f1a62e9716bb0b4ab774298ae2644c21f64b3a71870d7b1")
        self.assertEqual(source["license"],"UNSPECIFIED"); self.assertEqual(source["redistribution"],"prohibited-fail-closed")
        self.assertEqual(source["implementation"],"clean-room-from-public-markdown-description")
        self.assertFalse((SOURCE.parent/"upstream-main.py").exists()); self.assertFalse(source["default_enabled"]); self.assertEqual(source["kaggle_submission"],"NOT_PERFORMED")
        self.assertNotIn("structured-economic-policy",(ROOT/"main.py").read_text())
    def test_policy_and_measured_contract(self):
        text=ADAPTER.read_text()
        for invariant in ("demand_plan","sale_first","terminal_guard","labor_ceiling"): self.assertIn(invariant,text)
        evidence=json.loads(OUTPUT.read_text()); self.assertTrue(all(evidence["checks"].values())); self.assertEqual(evidence["screen"]["candidate"]["episodes"],4); self.assertTrue(evidence["screen"]["candidate"]["all_done"]); self.assertGreater(evidence["screen"]["attribution"]["paired_trace_divergences"],0); self.assertFalse(evidence["champion"]["modified"]); self.assertEqual(hashlib.sha256((ROOT/"main.py").read_bytes()).hexdigest(),evidence["champion"]["sha256"])
        if evidence["screen_gate"]=="PASS": self.assertTrue(evidence["confirm"]["candidate"]["all_done"]); self.assertEqual(evidence["confirm"]["candidate"]["episodes"],4)
if __name__ == "__main__": unittest.main()

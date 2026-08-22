import hashlib
import json
import unittest
from pathlib import Path

from scripts.measure_adaptive_farming_strategy import ADAPTER, OUTPUT, SOURCE

ROOT = Path(__file__).resolve().parents[1]


class AdaptiveFarmingStrategyTest(unittest.TestCase):
    def test_provenance_is_pinned_and_fail_closed(self):
        source = json.loads(SOURCE.read_text())
        self.assertEqual(source["notebook_sha256"], "ba18ed4f6077168a52850c31ad1a677b07bc6d1df1a942a40b52a113b2c0c1df")
        self.assertEqual(source["license"], "UNSPECIFIED")
        self.assertEqual(source["redistribution"], "prohibited-fail-closed")
        self.assertEqual(source["implementation"], "clean-room-from-public-markdown-description")
        self.assertFalse((SOURCE.parent / "upstream-main.py").exists())
        self.assertFalse(source["default_enabled"])
        self.assertEqual(source["kaggle_submission"], "NOT_PERFORMED")
        self.assertNotIn("adaptive-farming-strategy", (ROOT / "main.py").read_text())

    def test_route_source_and_measured_contract(self):
        text = ADAPTER.read_text()
        for route in ("yarn_first", "yarn_second", "yarn_third", "milk_support", "generalist"):
            self.assertIn(route, text)
        evidence = json.loads(OUTPUT.read_text())
        self.assertTrue(all(evidence["checks"].values()))
        self.assertEqual(evidence["screen"]["candidate"]["episodes"], 4)
        self.assertTrue(evidence["screen"]["candidate"]["all_done"])
        self.assertEqual(evidence["screen"]["attribution"]["paired_trace_divergences"], 4)
        self.assertEqual(evidence["source"]["kaggle_submission"], "NOT_PERFORMED")
        self.assertFalse(evidence["champion"]["modified"])
        self.assertEqual(hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest(), evidence["champion"]["sha256"])
        if evidence["screen_gate"] == "PASS":
            self.assertTrue(evidence["confirm"]["candidate"]["all_done"])
            self.assertEqual(evidence["confirm"]["candidate"]["episodes"], 4)


if __name__ == "__main__":
    unittest.main()

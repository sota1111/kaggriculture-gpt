import hashlib
import json
import unittest
from pathlib import Path

from scripts.measure_multi_route_farming_agent import ADAPTER, OUTPUT, SOURCE

ROOT = Path(__file__).resolve().parents[1]


class MultiRouteFarmingAgentTest(unittest.TestCase):
    def test_provenance_is_pinned_and_fail_closed(self):
        source = json.loads(SOURCE.read_text())
        self.assertEqual(source["notebook_sha256"], "50cc0b06b60f885d36b588609d6e7b165e96273625f4c57f402b9a3e13a570e6")
        self.assertEqual(source["license"], "UNSPECIFIED")
        self.assertEqual(source["redistribution"], "prohibited-fail-closed")
        self.assertEqual(source["implementation"], "clean-room-from-public-markdown-description")
        self.assertFalse((SOURCE.parent / "upstream-main.py").exists())
        self.assertFalse(source["default_enabled"])
        self.assertEqual(source["kaggle_submission"], "NOT_PERFORMED")
        self.assertNotIn("multi-route-farming-agent", (ROOT / "main.py").read_text())

    def test_route_source_and_measured_contract(self):
        text = ADAPTER.read_text()
        for route in ("yarn_led", "milk_supported", "balanced"):
            self.assertIn(route, text)
        evidence = json.loads(OUTPUT.read_text())
        self.assertTrue(all(evidence["checks"].values()))
        self.assertEqual(evidence["screen"]["candidate"]["episodes"], 4)
        self.assertTrue(evidence["screen"]["candidate"]["all_done"])
        self.assertEqual(evidence["screen"]["attribution"]["paired_trace_divergences"], 4)
        self.assertTrue(evidence["checks"]["all_route_families_fired"])
        self.assertEqual(set(evidence["route_family_holdout"]["targeted_probes"]),
                         {"yarn_led", "milk_supported", "balanced"})
        self.assertEqual(evidence["route_family_holdout"]["outcome_confirm"],
                         "identity-disjoint-sealed")
        self.assertEqual(evidence["source"]["kaggle_submission"], "NOT_PERFORMED")
        self.assertFalse(evidence["champion"]["modified"])
        self.assertEqual(hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest(), evidence["champion"]["sha256"])
        if evidence["screen_gate"] == "PASS":
            self.assertTrue(evidence["confirm"]["candidate"]["all_done"])
            self.assertEqual(evidence["confirm"]["candidate"]["episodes"], 4)


if __name__ == "__main__":
    unittest.main()

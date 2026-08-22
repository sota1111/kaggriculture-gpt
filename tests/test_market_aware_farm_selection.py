import hashlib
import json
import unittest
from pathlib import Path

from scripts.measure_market_aware_farm_selection import ADAPTER, OUTPUT, SOURCE

ROOT = Path(__file__).resolve().parents[1]


class MarketAwareFarmSelectionTest(unittest.TestCase):
    def test_provenance_is_pinned_and_fail_closed(self):
        source = json.loads(SOURCE.read_text())
        self.assertEqual(
            source["notebook_sha256"],
            "f0c7ccf2781f9287e5728e737e6ef3f72d047f66fa8dfeb33843146842ce1edd",
        )
        self.assertEqual(source["license"], "UNSPECIFIED")
        self.assertEqual(source["redistribution"], "prohibited-fail-closed")
        self.assertEqual(source["implementation"], "clean-room-from-public-description")
        self.assertFalse(source["default_enabled"])
        self.assertEqual(source["kaggle_submission"], "NOT_PERFORMED")
        self.assertFalse((SOURCE.parent / "upstream-main.py").exists())
        self.assertNotIn("market-aware-farm-selection", (ROOT / "main.py").read_text())

    def test_policy_and_measured_contract(self):
        for invariant in (
            "regime_observed",
            "dairy_farm",
            "fiber_farm",
            "produce_farm",
            "terminal_guard",
        ):
            self.assertIn(invariant, ADAPTER.read_text())
        evidence = json.loads(OUTPUT.read_text())
        self.assertTrue(all(evidence["checks"].values()))
        self.assertEqual(evidence["screen"]["candidate"]["episodes"], 4)
        self.assertGreater(
            evidence["screen"]["attribution"]["paired_trace_divergences"], 0
        )
        self.assertFalse(evidence["champion"]["modified"])
        self.assertEqual(
            hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest(),
            evidence["champion"]["sha256"],
        )
        if evidence["screen_gate"] == "PASS":
            self.assertEqual(evidence["confirm"]["candidate"]["episodes"], 4)
            self.assertTrue(evidence["confirm"]["candidate"]["all_done"])


if __name__ == "__main__":
    unittest.main()

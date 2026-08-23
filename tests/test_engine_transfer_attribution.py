import json
import unittest
from pathlib import Path

from scripts.measure_engine_transfer_attribution import current_field_association


class EngineTransferAttributionTest(unittest.TestCase):
    def test_current_field_metadata_stays_inconclusive(self):
        manifest = json.loads(Path("tests/fixtures/current_field_transfer_manifest.json").read_text())
        result = current_field_association(manifest)
        self.assertFalse(result["trajectory_available"])
        self.assertTrue(result["association_only_not_causal_attribution"])
        self.assertLess(result["pair_margin_drift"], 0)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from scripts.measure_v111_economic_core import ROOT, validate
from scripts.package_v111_economic_core import build


class V111EconomicCoreTest(unittest.TestCase):
    def test_provenance_and_sealed_manifest(self):
        fixture = json.loads((ROOT / "tests/fixtures/v111_economic_core.json").read_text())
        source = json.loads((ROOT / fixture["source_descriptor"]).read_text())
        checks = validate(fixture, source)
        self.assertTrue(all(checks.values()), checks)

    def test_package_is_single_file_and_champion_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "agent.py"
            result = build(artifact)
            self.assertFalse(result["champion_dependency"])
            self.assertIn("SHEEP_MAX = 4", artifact.read_text())
            self.assertNotEqual(artifact.read_bytes(), (ROOT / "main.py").read_bytes())

    def test_measurement_has_screen_confirm_firing_and_no_submission(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2981/SOT-2982-v111-economic-core.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertEqual({0, 1}, {r["seat"] for r in report["screen"]["candidate_rows"]})
        self.assertEqual({0, 1}, {r["seat"] for r in report["confirm"]["candidate_rows"]})
        self.assertTrue(report["firing"]["changed"])
        self.assertEqual(4, report["firing"]["sheep_target"])
        self.assertFalse(report["champion_hedge"]["modified"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

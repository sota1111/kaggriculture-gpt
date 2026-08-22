import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import measure_v16_rc5_whole_agent as measurement


class V16RC5MeasurementTest(unittest.TestCase):
    def test_extract_rejects_unpinned_notebook(self):
        with tempfile.TemporaryDirectory() as temp:
            notebook = Path(temp) / "source.ipynb"
            notebook.write_text(json.dumps({"cells": []}))
            with self.assertRaisesRegex(ValueError, "notebook SHA-256 mismatch"):
                measurement.extract_agent(notebook, Path(temp) / "main.py")

    def test_manifest_is_fail_closed_and_incumbent_is_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "candidates/v16_rc5/provenance.json").read_text())
        self.assertEqual("unknown", manifest["license"]["status"])
        self.assertEqual("fail-closed-no-redistribution", manifest["license"]["decision"])
        self.assertIsNone(manifest["packaging"]["candidate_artifact"])
        self.assertFalse(manifest["packaging"]["promotion_allowed"])
        self.assertEqual(manifest["incumbent"]["sha256_at_evaluation"],
                         hashlib.sha256((root / "main.py").read_bytes()).hexdigest())
        self.assertEqual("NOT_PERFORMED", manifest["kaggle_submission"])


if __name__ == "__main__":
    unittest.main()

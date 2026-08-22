import hashlib
import json
import unittest

from scripts.measure_kaito_v211_conditional_memory import OUTPUT, PACKAGE, SOURCE, validate


class KaitoV211ConditionalMemoryTest(unittest.TestCase):
    def test_provenance_license_and_strict_future_manifest(self):
        fixture = json.loads((PACKAGE.parents[1] / "tests/fixtures/kaito_v211_conditional_memory.json").read_text())
        source = json.loads(SOURCE.read_text())
        self.assertTrue(all(validate(fixture, source).values()), validate(fixture, source))
        self.assertFalse((PACKAGE / "main.py").exists())
        self.assertFalse((PACKAGE / "submission.tar.gz").exists())

    def test_memory_paths_and_sealed_evidence(self):
        report = json.loads(OUTPUT.read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("PASS", report["runtime_contract"])
        self.assertIn("no fixed sparse-history checkpoint", report["preregistered_difference_from_v39"])
        firing = report["candidate"]["targeted_firing"]
        self.assertTrue(firing["hit_fired"] and firing["miss_fired"] and firing["fallback_fired"])
        self.assertTrue(firing["unknown_preserved_base"])
        self.assertTrue(firing["sell_multiset_preserved"])
        self.assertEqual("PASS", report["screen_gate"])
        self.assertTrue(report["confirm"]["consumed"])
        self.assertTrue(report["confirm"]["candidate"]["all_done"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])
        self.assertFalse(report["champion"]["modified"])
        root = PACKAGE.parents[1]
        self.assertEqual(hashlib.sha256((root / "main.py").read_bytes()).hexdigest(), report["champion"]["sha256"])


if __name__ == "__main__":
    unittest.main()

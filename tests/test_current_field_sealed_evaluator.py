import copy
import json
import unittest
from pathlib import Path

from scripts.measure_current_field_sealed_evaluator import measure, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/fixtures/current_field_sealed_cohort.json").read_text())


class CurrentFieldSealedEvaluatorTest(unittest.TestCase):
    def test_manifest_is_immutable_disjoint_and_leak_free(self):
        result = validate_manifest(MANIFEST)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(result["checks"][f"{field}_disjoint"] for field in
                            ("opponent", "lineage", "episode", "seed", "time_slice")))
        self.assertTrue(result["checks"]["both_seats"])
        self.assertTrue(result["checks"]["identity_only_provenance"])

    def test_mutation_and_cross_stage_leak_fail_closed(self):
        changed = copy.deepcopy(MANIFEST)
        changed["cohort"]["cutoff_utc"] = "2026-08-23T00:00:00Z"
        self.assertFalse(validate_manifest(changed)["checks"]["cohort_hash_matches"])
        leaked = copy.deepcopy(MANIFEST)
        leaked["cohort"]["stages"]["stage_b"][0]["seed"] = \
            leaked["cohort"]["stages"]["stage_a"][0]["seed"]
        self.assertFalse(validate_manifest(leaked)["checks"]["seed_disjoint"])

    def test_screen_confirm_metrics_and_final_non_selection_are_machine_checked(self):
        report = measure(MANIFEST)
        self.assertTrue(report["passed"], report["validation"])
        self.assertEqual({"C95", "incumbent"}, set(report["stages"]["stage_a"]))
        self.assertTrue(report["stages"]["stage_b"]["C95"]["seat_pair_bootstrap_95"])
        self.assertFalse(report["final_holdout"]["opened"])
        self.assertFalse(report["final_holdout"]["used_for_selection"])
        self.assertEqual(["stage_a", "stage_b"], report["selection_inputs"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])

    def test_final_rows_cannot_contain_outcomes(self):
        leaked = copy.deepcopy(MANIFEST)
        leaked["cohort"]["stages"]["final_holdout"][0]["outcome"] = "W"
        self.assertFalse(validate_manifest(leaked)["checks"]["final_holdout_reserved"])


if __name__ == "__main__":
    unittest.main()

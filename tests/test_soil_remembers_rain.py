import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/soil-remembers-rain/agent.py"


class SoilRemembersRainTest(unittest.TestCase):
    def test_provenance_license_and_portable_contract(self):
        source = json.loads((CANDIDATE.parent / "source.json").read_text())
        self.assertEqual(source["script_version_id"], 344052698)
        self.assertEqual(source["kernel_version_number"], 21)
        self.assertEqual(source["license"], "Apache-2.0")
        self.assertEqual(source["dependencies"], ["python-standard-library"])
        self.assertEqual(hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(), source["packaged_agent_sha256"])
        self.assertEqual(source["packaged_agent_sha256"], source["output_main_sha256"])
        self.assertFalse(source["default_enabled"])
        self.assertEqual(source["kaggle_submission"], "NOT_PERFORMED")
        spec = importlib.util.spec_from_file_location("soil_candidate", CANDIDATE)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.agent))

    def test_screen_confirm_evidence_and_champion_hedge(self):
        evidence = json.loads((ROOT / "docs/measurements/SOT-2971/SOT-2973-soil-remembers-rain.json").read_text())
        self.assertIn(evidence["screen_gate"], {"PASS", "FAIL"})
        self.assertIn(evidence["decision"], {"promoted", "rejected", "inconclusive"})
        self.assertTrue(evidence["checks"]["same_seed_both_seats"])
        self.assertTrue(evidence["checks"]["opponent_seed_time_disjoint"])
        self.assertTrue(evidence["screen"]["candidate"]["all_done"])
        self.assertEqual(evidence["screen"]["candidate"]["episodes"], 4)
        self.assertGreater(evidence["screen"]["candidate"]["non_pass_actions"], 0)
        self.assertEqual(evidence["screen"]["intervention"]["action_trace_divergences"], 4)
        if evidence["screen_gate"] == "PASS":
            self.assertIsInstance(evidence["confirm"], dict)
            self.assertTrue(evidence["confirm"]["candidate"]["all_done"])
            self.assertEqual(evidence["confirm"]["candidate"]["episodes"], 4)
            self.assertGreater(evidence["confirm"]["candidate"]["non_pass_actions"], 0)
            self.assertEqual(evidence["confirm"]["intervention"]["action_trace_divergences"], 4)
        else:
            self.assertEqual(evidence["confirm"], "RESERVED_UNOPENED")
            self.assertEqual(evidence["decision"], "inconclusive")
        self.assertFalse(evidence["champion"]["modified"])
        self.assertEqual(hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest(), evidence["champion"]["sha256"])


if __name__ == "__main__":
    unittest.main()

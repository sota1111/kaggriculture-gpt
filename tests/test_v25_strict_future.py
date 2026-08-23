import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

from scripts.measure_v25_strict_future import static_audit

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/v25-strict-future-cleanroom/agent.py"
SOURCE = ROOT / "candidates/v25-strict-future-cleanroom/source.json"
EVIDENCE = ROOT / "docs/measurements/SOT-3033/v25-screen-confirm.json"


class V25StrictFutureTest(unittest.TestCase):
    def test_provenance_identity_and_static_boundary(self):
        source = json.loads(SOURCE.read_text())
        self.assertEqual(source["license"], "Apache-2.0")
        self.assertEqual(source["script_version_id"], 341206423)
        self.assertEqual(source["notebook_sha256"], "e28aa997dc5317cad8e2a8ee5887efa7c12c40fc17e41af366f2723f29f21406")
        self.assertIn("719-action replay-reconstructed backbone", source["excluded"])
        self.assertTrue(all(static_audit(CANDIDATE)[key] for key in
                            ("compiles", "no_large_action_lookup", "no_sensitive_runtime_tokens", "no_network_import")))

    def test_independent_whole_agent_contract(self):
        source = json.loads(SOURCE.read_text())
        self.assertEqual(hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
                         "5db1a9e17227ee7b049bafd12c0d758b9a210df1b9c1ef2124767e583fcbfc02")
        self.assertNotIn("main.py", CANDIDATE.read_text())
        spec = importlib.util.spec_from_file_location("v25_candidate", CANDIDATE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.agent))
        self.assertFalse(source["default_enabled"])
        self.assertEqual(source["kaggle_submission"], "NOT_PERFORMED")

    def test_screen_and_sealed_confirm(self):
        report = json.loads(EVIDENCE.read_text())
        self.assertTrue(report["passed"])
        self.assertTrue(report["runtime_contract_passed"])
        self.assertTrue(report["submission_contract_passed"])
        self.assertTrue(all(report["isolation"].values()))
        self.assertIn(report["decision"], {"promoted", "inconclusive"})
        self.assertEqual(report["kaggle_submission"], "NOT_PERFORMED")
        for cohort in ("screen", "confirm"):
            self.assertTrue(report[cohort]["summary"]["all_done"])
            self.assertEqual(report[cohort]["summary"]["invalid_actions"], 0)


if __name__ == "__main__":
    unittest.main()

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/c95-high-score/agent.py"
EVIDENCE = ROOT / "docs/measurements/SOT-3004/c95-screen-confirm.json"
READINESS = ROOT / "docs/measurements/SOT-3016/c95-screen-confirm-rerun.json"


class C95HighScoreTest(unittest.TestCase):
    def test_exact_identity_and_contract(self):
        source = json.loads((CANDIDATE.parent / "source.json").read_text())
        self.assertEqual(source["license"], "Apache-2.0")
        self.assertEqual(CANDIDATE.stat().st_size, source["packaged_size"])
        self.assertEqual(hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(), source["packaged_agent_sha256"])
        self.assertEqual(source["runtime_external_dependencies"], [])
        self.assertFalse(source["default_enabled"])
        self.assertEqual(source["kaggle_submission"], "NOT_PERFORMED")
        spec = importlib.util.spec_from_file_location("c95_candidate", CANDIDATE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.agent))

    def test_sealed_evidence(self):
        evidence = json.loads(EVIDENCE.read_text())
        self.assertEqual(evidence["screen_gate"], "PASS")
        self.assertIn(evidence["decision"], {"promoted", "inconclusive"})
        self.assertTrue(all(evidence["isolation"].values()))
        self.assertTrue(evidence["runtime_contract_passed"])
        self.assertEqual(evidence["artifact"]["bytes"], 133270)
        self.assertTrue(evidence["checks"]["no_submission"])
        for cohort in ("screen", "confirm"):
            self.assertTrue(evidence[cohort]["summary"]["all_done"])
            self.assertEqual(evidence[cohort]["summary"]["invalid_actions"], 0)
            self.assertGreater(evidence[cohort]["summary"]["non_pass_actions"], 0)

    def test_immutable_submission_readiness_rerun(self):
        baseline = json.loads(EVIDENCE.read_text())
        readiness = json.loads(READINESS.read_text())
        source = json.loads((CANDIDATE.parent / "source.json").read_text())
        self.assertEqual(readiness["issue"], "SOT-3016")
        self.assertEqual(readiness["artifact"]["sha256"], source["packaged_agent_sha256"])
        self.assertEqual(
            readiness["effective_config_fingerprint"],
            "cd276b276df40fdd4c0c8b855991b1f59e0c3634db997af24e5eb8b434c1d04a",
        )
        self.assertFalse(readiness["champion"]["modified"])
        self.assertEqual(readiness["screen_gate"], "PASS")
        self.assertTrue(readiness["runtime_contract_passed"])
        self.assertEqual(readiness["decision"], "promoted")
        for cohort in ("screen", "confirm"):
            expected = [row["action_trace_sha256"] for row in baseline[cohort]["candidate_rows"]]
            actual = [row["action_trace_sha256"] for row in readiness[cohort]["candidate_rows"]]
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidates/kaito-v19-replication-control/agent.py"


class KaitoV19ReplicationControlTest(unittest.TestCase):
    def test_provenance_license_and_portable_contract(self):
        source = json.loads((CANDIDATE.parent / "source.json").read_text())
        self.assertEqual(source["script_version_id"], 340133955)
        self.assertEqual(source["license"], "Apache-2.0")
        self.assertEqual(source["dependencies"], ["python-standard-library"])
        self.assertEqual(hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(), source["packaged_agent_sha256"])
        self.assertFalse(source["default_enabled"])
        self.assertEqual(source["kaggle_submission"], "NOT_PERFORMED")
        spec = importlib.util.spec_from_file_location("v19_candidate", CANDIDATE)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.agent))

    def test_lineage_holdout_evidence_and_champion_hedge(self):
        evidence = json.loads((ROOT / "docs/measurements/SOT-2971/SOT-2974-kaito-v19-replication-control.json").read_text())
        self.assertTrue(evidence["checks"]["same_seed_both_seats"])
        self.assertTrue(evidence["checks"]["opponent_episode_seed_seat_time_disjoint"])
        self.assertTrue(evidence["checks"]["no_private_trace_shipped"])
        self.assertFalse(evidence["novelty_vs_v39"]["same_intervention"])
        self.assertEqual(evidence["screen_gate"], "PASS")
        self.assertIn(evidence["decision"], {"promoted", "inconclusive"})
        for cohort in ("screen", "confirm"):
            self.assertNotEqual(evidence[cohort], "RESERVED_UNOPENED")
            self.assertTrue(evidence[cohort]["candidate"]["all_done"])
            self.assertEqual(evidence[cohort]["candidate"]["episodes"], 4)
            self.assertGreater(evidence[cohort]["candidate"]["non_pass_actions"], 0)
        self.assertFalse(evidence["champion"]["modified"])
        self.assertEqual(hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest(), evidence["champion"]["sha256"])


if __name__ == "__main__":
    unittest.main()

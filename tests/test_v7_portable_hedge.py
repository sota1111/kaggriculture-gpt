import hashlib
import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.package_v7_portable_hedge import DESCRIPTOR, build


ROOT = Path(__file__).resolve().parents[1]


class V7PortableHedgeTest(unittest.TestCase):
    def test_committed_screen_preserves_champion_and_parent_confirm(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2934/"
                             "SOT-2939-v7-portable-hedge.json").read_text())
        self.assertEqual("retain-descriptor-only-license-blocked", report["decision"])
        self.assertFalse(report["license_gate"]["passed"])
        self.assertFalse(report["champion"]["modified"])
        self.assertFalse(report["public_score_used_for_promotion"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])
        self.assertEqual("RESERVED_FOR_PARENT_PORTFOLIO_CHILD",
                         report["private_proxy_screen"]["confirm_status"])
        self.assertEqual(4, len(report["private_proxy_screen"]["paired_rows"]))
        self.assertTrue(all(row["candidate_statuses"] == ["DONE", "DONE"]
                            for row in report["private_proxy_screen"]["paired_rows"]))

    def test_descriptor_keeps_unlicensed_whole_agent_out_of_repository(self):
        descriptor = json.loads(DESCRIPTOR.read_text())
        self.assertEqual("not-authorized-for-whole-agent", descriptor["redistribution"])
        self.assertEqual("NOT_PERFORMED", descriptor["kaggle_submission"])
        self.assertFalse((ROOT / "candidates/v7-portable/main.py").exists())
        self.assertEqual(64, len(descriptor["sha256"]))

    def test_exact_checkout_builds_deterministic_offline_archive(self):
        descriptor = json.loads(DESCRIPTOR.read_text())
        source_path_file = ROOT / ".ai-jobs/sot-2939-source-path.txt"
        if not source_path_file.exists():
            self.skipTest("exact upstream checkout is not available")
        source = Path(source_path_file.read_text().strip())
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.tar.gz"
            second = Path(directory) / "second.tar.gz"
            report = build(source, first)
            build(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), report["archive_sha256"])
            with tarfile.open(first, "r:gz") as archive:
                self.assertEqual(
                    ["LICENSE-APACHE-2.0.txt", "THIRD_PARTY_NOTICES.txt", "main.py"],
                    archive.getnames(),
                )
                agent_bytes = archive.extractfile("main.py").read()
            self.assertEqual(descriptor["sha256"], hashlib.sha256(agent_bytes).hexdigest())

    def test_exact_agent_contract_is_json_safe(self):
        source_path_file = ROOT / ".ai-jobs/sot-2939-source-path.txt"
        if not source_path_file.exists():
            self.skipTest("exact upstream checkout is not available")
        agent_path = Path(source_path_file.read_text().strip()) / "main.py"
        spec = importlib.util.spec_from_file_location("v7_portable_contract", agent_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        observation = {
            "player": 0,
            "step": 0,
            "day": 0,
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
            "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[]]},
        }
        action = module.agent(observation)
        json.dumps(action)
        self.assertEqual({"farmer", "hands", "market"}, set(action))
        self.assertTrue(all(isinstance(action[key], list) for key in action))


if __name__ == "__main__":
    unittest.main()

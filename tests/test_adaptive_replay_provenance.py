import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_adaptive_replay_provenance import validate

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "candidates/adaptive-replay-audit/source.json"


class AdaptiveReplayProvenanceTest(unittest.TestCase):
    def test_fetch_only_boundary_is_complete(self):
        source = json.loads(SOURCE_PATH.read_text())
        self.assertTrue(all(validate(source).values()), validate(source))

    def test_no_upstream_executable_or_replay_is_vendored(self):
        names = {path.name for path in SOURCE_PATH.parent.iterdir()}
        self.assertEqual({"README.md", "source.json"}, names)
        descriptor = SOURCE_PATH.read_text()
        self.assertNotIn("_ACTIONS =", descriptor)
        self.assertNotIn("AGENT_SOURCE", descriptor)

    def test_transient_hash_check_fails_closed(self):
        source = json.loads(SOURCE_PATH.read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / source["notebook_filename"]).write_text("wrong")
            (root / "kernel-metadata.json").write_text("wrong")
            checks = validate(source, root)
        self.assertFalse(checks["transient_notebook_hash_matches"])
        self.assertFalse(checks["transient_metadata_hash_matches"])


if __name__ == "__main__":
    unittest.main()

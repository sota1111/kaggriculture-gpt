import json, tempfile, unittest
from pathlib import Path
from unittest import mock
from scripts.evaluation.economic_oracle import (ENGINE_VERSION, SNAPSHOT, EngineDriftError,
    GapRecord, action_family, derive_snapshot, validate_snapshot)

class EconomicOracleTest(unittest.TestCase):
    def test_snapshot_matches_official_engine_identities(self):
        snap=validate_snapshot()
        self.assertEqual(ENGINE_VERSION, snap["engine"]["version"])
        self.assertEqual([1000,2000,4000], snap["land"]["prices"])
        self.assertEqual([1,1,2,3,5,8,13,21,34,55], snap["labor"]["daily_hire_costs_first_10"])
        self.assertEqual(718, snap["execution"]["last_action_step"])
        self.assertEqual(100, snap["shed"]["default_capacity"])

    def test_market_and_crop_identities_are_engine_derived(self):
        snap=derive_snapshot()
        for row in snap["market"].values():
            self.assertEqual(row["base"], row["price_at_i0"])
            self.assertGreaterEqual(row["price_at_i0_minus_t"], row["price_at_i0"])
            self.assertLessEqual(row["price_at_i0_plus_t"], row["price_at_i0"])
        self.assertEqual(90, snap["crops"]["WHEAT"]["base_profit"])
        self.assertGreater(snap["crops"]["WHEAT"]["fertilizer_increment_value"], 0)
        self.assertEqual(160, snap["animals"]["COW"]["care_bonus_value_per_fed_day"])

    def test_version_and_snapshot_drift_fail_closed(self):
        with mock.patch("importlib.metadata.version", return_value="9.9.9"):
            with self.assertRaises(EngineDriftError): derive_snapshot()
        bad=json.loads(SNAPSHOT.read_text()); bad["shed"]["default_capacity"]=99
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.json"; p.write_text(json.dumps(bad))
            with self.assertRaises(EngineDriftError): validate_snapshot(p)

    def test_gap_dimensions_and_action_families(self):
        row=GapRecord("incumbent","starter","main",1,0,100,25,20,"crop")
        self.assertEqual(-5,row.gap)
        self.assertEqual("market-capital",action_family({"farmer":["PASS"],"hands":[],"market":[["SELL","WHEAT",1]]}))
        self.assertEqual("animal",action_family({"farmer":["CARE"],"hands":[],"market":[]}))

if __name__ == "__main__": unittest.main()

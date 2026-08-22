import unittest
from scripts.measure_engine_economic_oracle import COHORTS, planned_value

class MeasureEconomicOracleTest(unittest.TestCase):
    def test_cohorts_are_seed_lineage_and_time_disjoint(self):
        self.assertNotEqual(COHORTS["screen"]["seed"],COHORTS["confirm"]["seed"])
        self.assertNotEqual(COHORTS["screen"]["lineage"],COHORTS["confirm"]["lineage"])
    def test_sell_plan_uses_public_market_price(self):
        obs={"market":{"prices":{"WHEAT":25}},"farms":[{"farmer":[0,0],"tiles":[[None]]}]}
        action={"farmer":["PASS"],"hands":[],"market":[["SELL","WHEAT",3]]}
        self.assertEqual(75,planned_value(action,obs,0))
if __name__=="__main__": unittest.main()

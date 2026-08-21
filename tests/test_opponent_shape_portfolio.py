import importlib.util, json, unittest
from pathlib import Path
from scripts.measure_opponent_shape_portfolio import ROOT, validate

class OpponentShapePortfolioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/"candidates/opponent-shape-portfolio/agent.py"
        spec=importlib.util.spec_from_file_location("shape_test",path); cls.module=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.module)
    def obs(self,tile):
        return {"player":0,"day":3,"step":72,"farms":[{"tiles":[[None]],"farmer":[0,0],"hands":[]},{"tiles":[[tile,None,None,None,None]],"farmer":[0,0],"hands":[]}]}
    def test_public_shape_routes_are_reachable(self):
        self.assertEqual("contract_farmer",self.module.select_foundation(self.obs(None)))
        self.assertEqual("field_scheduler",self.module.select_foundation(self.obs({"kind":"PLANT"})))
        animal={"kind":"ANIMAL"}; obs=self.obs(animal); obs["farms"][1]["tiles"]=[[animal,animal,None]]
        self.assertEqual("champion",self.module.select_foundation(obs))
    def test_registered_holdout(self):
        cfg=json.loads((ROOT/"tests/fixtures/opponent_shape_portfolio.json").read_text())
        self.assertTrue(all(validate(cfg).values()))
    def test_selector_source_has_no_private_or_score_input(self):
        source=(ROOT/"candidates/opponent-shape-portfolio/agent.py").read_text()
        self.assertNotIn('obs.get("private"',source); self.assertNotIn("public_score",source)
if __name__=="__main__": unittest.main()

import unittest

from scripts.evaluation.economic_oracle import EngineDriftError, validate_snapshot
from scripts.evaluation.trajectory_attribution import IDENTITIES, inventory, planned_values, transition


def obs(money=100, shed=None, price=25):
    return {"private":{"shed":shed or {"WHEAT":0},"seeds":{"WHEAT":0},"inventories":[{}]},
            "market":{"prices":{"WHEAT":price}},"farms":[{"money":money,"tiles":[[None]]}],
            "town":{"unlocked_shops":[]}}


class TrajectoryAttributionTest(unittest.TestCase):
    def setUp(self): self.snapshot = validate_snapshot()

    def test_transition_has_every_identity_and_recalculates_gap(self):
        before, after = obs(shed={"WHEAT":2}), obs(shed={"WHEAT":1}, price=30)
        rows = transition(before, after, {"farmer":["PASS"],"hands":[],"market":[]}, 0,
                          self.snapshot, end_of_day=False)
        self.assertEqual(set(IDENTITIES), set(rows))
        for row in rows.values(): self.assertEqual(row["realized"] - row["planned"], row["gap"])

    def test_planning_uses_engine_seed_identity(self):
        values = planned_values({"market":[["BUY_SEED","WHEAT",3]]}, obs(), self.snapshot)
        self.assertEqual(3 * self.snapshot["crops"]["WHEAT"]["seed"], values["terminal_inventory"])

    def test_missing_or_forbidden_private_state_fails_closed(self):
        with self.assertRaises(EngineDriftError): inventory({"market":{"prices":{}}})
        bad = obs(); bad["opponent_private"] = {}
        with self.assertRaises(EngineDriftError): inventory(bad)


if __name__ == "__main__": unittest.main()

import unittest

from scripts.evaluation.economic_oracle import EngineDriftError, validate_snapshot
from scripts.evaluation.trajectory_attribution import (
    IDENTITIES, interaction_transition, inventory, market_terminal_identity,
    planned_values, transition,
)


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

    def test_market_terminal_engine_identity_is_exact(self):
        state = obs(shed={"WHEAT": 3}, price=30)
        values = market_terminal_identity(state, self.snapshot)
        self.assertEqual(75, values["terminal_base"])
        self.assertEqual(15, values["market_impact"])
        self.assertEqual(90, values["market_value"])
        self.assertEqual(0, values["identity_residual"])

    def test_market_terminal_and_opponent_interactions_fire(self):
        before = obs(shed={"WHEAT": 2}, price=25)
        after = obs(shed={"WHEAT": 3}, price=30)
        before["farms"].append({"money": 100, "tiles": [[None]]})
        after["farms"].append({"money": 80, "tiles": [[None]]})
        after["farms"][0]["money"] = 110
        values = interaction_transition(before, after, 0, self.snapshot)
        self.assertTrue(values["market_terminal_fired"])
        self.assertTrue(values["opponent_exposure_fired"])
        self.assertEqual(0, values["identity_residual"])


if __name__ == "__main__": unittest.main()

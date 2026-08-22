import unittest
from dataclasses import replace
from unittest import mock

from scripts.evaluation.sealed import (EnginePin, MatchResult, SealedProtocol,
                                       evaluate_sealed, validate_engine, validate_protocol)


PIN = EnginePin("kaggle-environments", "1.32.7",
                "28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c",
                "61f1d031afceb5ea3324918723941e0ea2dcc89c8190a64d6837d9fb8a7e53c0",
                "shared-market-lockstep-precommit-unit-quotes-v1",
                "farmer-hands-market-orders-kaggriculture-v1")
PROTOCOL = SealedProtocol(PIN, (300701, 300703), (300711, 300713),
                          (300721, 300723), ("incumbent", "hamburger"), 200, 7)


class SealedEvaluationTest(unittest.TestCase):
    def test_seed_blocks_are_non_overlapping_and_fingerprinted(self):
        self.assertTrue(validate_protocol(PROTOCOL)["passed"])
        self.assertEqual(PROTOCOL.fingerprint(), PROTOCOL.fingerprint())
        self.assertFalse(validate_protocol(replace(PROTOCOL, final_seeds=(300701,)))["passed"])

    @mock.patch("importlib.metadata.version", return_value="1.32.7")
    def test_engine_and_semantics_mismatch_fail_closed(self, _version):
        self.assertTrue(validate_engine(PIN, PIN)["passed"])
        result = validate_engine(replace(PIN, pricing_semantics="wrong"), PIN)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["pricing_semantics"])

    def test_both_seats_multiple_opponents_bootstrap_and_final_is_sealed(self):
        calls = []
        def runner(candidate, opponent, seed, seat, block):
            calls.append((candidate, opponent, seed, seat, block))
            margin = 5 if candidate == "good" else -2
            return MatchResult(block, candidate, opponent, seed, seat, margin, 0)
        result = evaluate_sealed(PROTOCOL, ("bad", "good"), runner)
        self.assertEqual("good", result["selected_before_final"])
        self.assertFalse(result["final_used_for_selection"])
        self.assertEqual({0, 1}, {row[3] for row in calls})
        self.assertEqual(set(PROTOCOL.opponents), {row[1] for row in calls})
        self.assertTrue(result["candidates"]["good"]["confirm"]["bootstrap_95"])

    def test_technical_failure_and_incomplete_seat_pair_cannot_promote(self):
        def runner(candidate, opponent, seed, seat, block):
            status = "ERROR" if candidate == "broken" and seat == 1 else "DONE"
            return MatchResult(block, candidate, opponent, seed, seat, 10, 0, status)
        result = evaluate_sealed(PROTOCOL, ("broken",), runner)
        self.assertEqual("no-promotion", result["decision"])
        self.assertFalse(result["candidates"]["broken"]["screen"]["promotion_eligible"])

    def test_candidate_exception_becomes_fail_closed_fallback(self):
        def runner(*_args):
            raise RuntimeError("candidate exploded")
        result = evaluate_sealed(PROTOCOL, ("broken",), runner)
        self.assertEqual("no-promotion", result["decision"])
        self.assertTrue(result["candidates"]["broken"]["screen"]["technical_failure"])

    def test_worst_opponent_regression_vetoes_after_pre_final_selection(self):
        def runner(candidate, opponent, seed, seat, block):
            margin = -1 if block == "final" and opponent == "hamburger" else 4
            return MatchResult(block, candidate, opponent, seed, seat, margin, 0)
        result = evaluate_sealed(PROTOCOL, ("candidate",), runner)
        self.assertEqual("rejected-final", result["decision"])
        self.assertFalse(result["worst_opponent_guard"])


if __name__ == "__main__":
    unittest.main()

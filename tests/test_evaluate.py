import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.evaluate import bounded_rollout, compare, compare_distribution, evaluate, evaluate_opponent_policy, evaluate_paired_cv, evaluate_scenarios, load_agent, run_competitive_market, run_episode, validate_authenticated_replay_cv, validate_cv_holdouts
from scripts import evaluate as evaluator
from scripts.measure_leak_free_cv import canonical_sha256, fetch_artifacts, measure, raw_url, validate_corpus_manifest
from scripts.measure_live_lb_reanchor import measure as measure_live_lb_reanchor
from scripts.measure_demand_premium_sales import _gate as demand_premium_gate
from scripts.measure_multi_step_transition_oracle import measure as measure_transition_oracle, validate_split
from scripts.build_replay_teacher_dataset import public_projection, validate_manifest as validate_teacher_manifest
from scripts.distill_compact_replay_policy import distill as distill_compact_policy
from scripts.measure_compact_replay_policy import targeted_trace as compact_targeted_trace
from scripts.measure_compact_policy_sealed_gate import measure as measure_compact_sealed_gate
from scripts.measure_fertilizer_coverage import classify_bottleneck
from scripts.measure_care_livestock import evaluate as evaluate_care, load_policy as load_care_policy
from scripts.measure_post_repair_cash_flow import measure as measure_post_repair_cash_flow
from scripts.measure_runway_acreage import _gate as runway_gate, _targeted_trace
from scripts.measure_productive_action_capacity import _gate as capacity_gate, _targeted_trace as capacity_trace
from scripts.measure_public_action_capacity_oracle import measure as measure_public_capacity, validate_fixture as validate_capacity_fixture
from scripts.measure_public_closed_loop_holdout import validate_manifest as validate_closed_loop_manifest
from scripts.measure_decision_family_divergence import _family as decision_family, first_actions
from scripts.measure_feed_economic_decision import targeted_trace as feed_economic_trace
from scripts.measure_feed_economic_sealed_panel import gate as feed_sealed_gate, panel_checks
from scripts.measure_sequence_precursor_sealed_panel import gate as precursor_sealed_gate
from scripts.measure_winner_sequence_support import measure as measure_winner_sequence_support
from scripts.measure_sequence_planner import measure as measure_sequence_planner, planner_observation
from scripts.measure_sequence_planner_sealed_panel import gate as sequence_planner_sealed_gate


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/evaluation.json").read_text())


class EvaluationTest(unittest.TestCase):
    def test_public_action_capacity_oracle_is_leak_free_deterministic_and_both_seat(self):
        fixture = json.loads((ROOT / "tests/fixtures/public_action_capacity_oracle.json").read_text())
        first = measure_public_capacity(ROOT / "main.py", fixture)
        second = measure_public_capacity(ROOT / "main.py", fixture)
        self.assertEqual(first, second)
        self.assertTrue(first["passed"], first)
        self.assertTrue(all(first["split"]["checks"].values()))
        self.assertEqual("RECEDING_HORIZON_SEQUENCE_PLANNER=false",
                         first["same_seed_baseline_results"]["configuration"])
        for window in ("screen", "confirm"):
            self.assertEqual([0, 1], first[window]["both_seats"])
            self.assertGreater(first[window]["totals"]["productive_tasks"], 0)
            self.assertGreater(first[window]["totals"]["mandatory_travel_steps"], 0)
            self.assertGreater(first[window]["totals"]["route_repair_assignments"], 0)
            for episode in first[window]["episodes"]:
                for turn in episode["turns"]:
                    self.assertIn("capacity_utilization", turn)
                    self.assertIn("productive_density", turn)
        self.assertEqual("NOT_PERFORMED", first["kaggle_submission"])

    def test_public_action_capacity_oracle_fails_closed_on_leakage(self):
        fixture = json.loads((ROOT / "tests/fixtures/public_action_capacity_oracle.json").read_text())
        fixture["screen"][0]["observations"][0]["private"] = {"seeds": {"WHEAT": 99}}
        self.assertFalse(validate_capacity_fixture(fixture)["passed"])
        report = measure_public_capacity(ROOT / "main.py", fixture)
        self.assertFalse(report["passed"])
        self.assertTrue(report["confirm"]["skipped"])
        self.assertEqual("inconclusive", report["result"])

    def test_sequence_planner_sealed_gate_requires_rank_and_live_multistep_firing(self):
        run = {"rank": 1, "states": 720, "statuses": ["DONE", "DONE"],
               "invalid_actions": 0, "contract_violations": 0, "stderr": "", "seconds": 1.0,
               "capacity_violations": 0}
        candidate = {**run, "planner": {"firings": 0, "multi_step_firings": 0, "repairs": 0}}
        window = {"summary": {
            "mean_rank_improvement": 0, "mean_reward_delta": 10,
            "lower_tail_reward_delta": 0, "worst_reward_delta": 0,
            "mean_margin_delta": 10, "lower_tail_margin_delta": 0,
            "worst_margin_delta": 0, "planner_firings": 0, "multi_step_firings": 0,
            "capacity_violations": 0, "invalid_actions": 0, "contract_violations": 0,
        }, "raw_rows": [{"identity": {"episode_id": "screen"},
                           "champion": run, "candidate": candidate}]}
        passed, reasons, runtime = sequence_planner_sealed_gate(
            window, {"rank": 0, "reward": 0, "margin": 0}, 2.0)
        self.assertFalse(passed)
        self.assertIn("primary rank KPI did not improve beyond deterministic noise width", reasons)
        self.assertIn("planner did not fire as a multi-step intervention in closed loop", reasons)
        self.assertFalse(runtime["primary_kpi_beyond_noise"]["rank"])

    def test_receding_horizon_planner_ablation_fires_both_seats_and_changes_sequence(self):
        fixture = json.loads((ROOT / "tests/fixtures/sequence_planner_panel.json").read_text())
        report = measure_sequence_planner(ROOT / "main.py", fixture)
        self.assertTrue(report["passed"], report)
        for panel in ("screen", "confirm"):
            self.assertTrue(report[panel]["both_seats"])
            self.assertGreaterEqual(report[panel]["intervention_steps"], 4)
            self.assertGreaterEqual(report[panel]["multi_step_firings"], 2)
            self.assertEqual(0, report[panel]["invalid_actions"])
            self.assertEqual(0, report[panel]["contract_violations"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])

    def test_receding_horizon_planner_hard_constraints_and_tie_break_are_deterministic(self):
        agent = load_agent(ROOT / "main.py")
        obs = planner_observation(0, 24)
        baseline = [["PASS"], ["PASS"]]
        first = agent._sequence_planner_actions(
            json.loads(json.dumps(obs)), baseline, "WHEAT", agent._crop_specs(obs))
        second = agent._sequence_planner_actions(
            json.loads(json.dumps(obs)), baseline, "WHEAT", agent._crop_specs(obs))
        self.assertEqual(first, second)
        constrained = json.loads(json.dumps(obs))
        constrained["private"]["seeds"]["WHEAT"] = 0
        constrained["total_days"] = constrained["day"]
        actions = agent._sequence_planner_actions(
            constrained, baseline, "WHEAT", agent._crop_specs(constrained))
        self.assertNotIn("PLANT", [action[0] for action in actions])

    def test_multi_step_oracle_is_isolated_deterministic_and_measures_all_capacities(self):
        fixture = json.loads((ROOT / "tests/fixtures/multi_step_transition_oracle.json").read_text())
        first = measure_transition_oracle(ROOT / "main.py", fixture)
        second = measure_transition_oracle(ROOT / "main.py", fixture)
        self.assertEqual(first, second)
        self.assertTrue(first["passed"], first)
        self.assertEqual([0, 1], sorted(first["screen"]["both_seat_evidence"]))
        self.assertEqual([0, 1], sorted(first["confirm"]["both_seat_evidence"]))
        for window in ("screen", "confirm"):
            self.assertEqual({"labor", "travel", "cash", "seed", "shed", "action"},
                             set(first[window]["capacity_violations"]))
            self.assertEqual({"task", "locations", "inventory"},
                             set(first[window]["transition_counts"]))
        self.assertEqual("NOT_PERFORMED", first["kaggle_submission"])

    def test_multi_step_oracle_rejects_private_future_trace_and_skips_confirm(self):
        fixture = json.loads((ROOT / "tests/fixtures/multi_step_transition_oracle.json").read_text())
        fixture["screen"][0]["future"] = {"winner_action": ["BUILD_PASTURE"]}
        split = validate_split(fixture)
        self.assertFalse(split["passed"])
        self.assertFalse(split["checks"]["winner_trace_is_provenance_only"])
        report = measure_transition_oracle(ROOT / "main.py", fixture)
        self.assertTrue(report["confirm"]["skipped"])

    def test_winner_sequence_support_manifest_and_measurement_are_leak_free(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/winner_sequence_support_manifest.json").read_text()
        )
        report = json.loads(
            (ROOT / "docs/measurements/SOT-2835/SOT-2836-winner-sequence-support.json").read_text()
        )
        self.assertTrue(report["passed"])
        self.assertTrue(all(report["checks"].values()), report["checks"])
        self.assertEqual(manifest["dataset_sha256"], report["provenance"]["dataset_sha256"])
        self.assertEqual({0, 1}, {row["winner_seat"] for row in manifest["entries"]})
        self.assertEqual("task", report["confirm"]["stable_first_precursor"])
        self.assertGreater(report["screen"]["sequence_support_gap"], 0)
        self.assertGreater(report["confirm_panel"]["sequence_support_gap"], 0)
        self.assertIn("no causal uplift", report["causal_boundary"])
        self.assertFalse(report["runtime_candidate_changed"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])

    def test_winner_sequence_support_fails_closed_on_dataset_digest_drift(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/winner_sequence_support_manifest.json").read_text()
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl") as dataset:
            dataset.write("{}\n")
            dataset.flush()
            report = measure_winner_sequence_support(
                Path(dataset.name), manifest, ROOT / "main.py", manifest["dataset_sha256"]
            )
        self.assertFalse(report["passed"])
        self.assertTrue(report["confirm"]["skipped"])
        self.assertFalse(report["checks"]["dataset_digest"])

    def test_feed_economic_sealed_panel_holds_out_every_split_dimension(self):
        manifest = json.loads((ROOT / "tests/fixtures/feed_economic_sealed_panel.json").read_text())
        checks = panel_checks(manifest)
        self.assertTrue(all(checks.values()), checks)
        self.assertEqual("NOT_PERFORMED", manifest["kaggle_submission"])

    def test_feed_economic_sealed_gate_requires_live_intervention_and_kpi_uplift(self):
        run = {"rank": 1, "states": 720, "statuses": ["DONE", "DONE"],
               "invalid_actions": 0, "contract_violations": 0, "stderr": "", "seconds": 1.0}
        candidate = {**run, "feed_economic_firings": 0}
        window = {"summary": {
            "mean_rank_improvement": 0, "mean_reward_delta": 0,
            "lower_tail_reward_delta": 0, "worst_reward_delta": 0,
            "mean_margin_delta": 0, "lower_tail_margin_delta": 0,
            "worst_margin_delta": 0, "candidate_interventions": 0,
            "invalid_actions": 0, "contract_violations": 0,
        }, "raw_rows": [{"identity": {"episode_id": "screen"},
                           "champion": run, "candidate": candidate}]}
        passed, reasons, runtime = feed_sealed_gate(
            window, {"rank": 0, "reward": 0, "margin": 0}, 2.0)
        self.assertFalse(passed)
        self.assertIn("candidate produced no live intervention", reasons)
        self.assertFalse(any(runtime["primary_kpi_beyond_noise"].values()))

    def test_sequence_precursor_sealed_panel_holds_out_every_split_dimension(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/sequence_precursor_sealed_panel.json").read_text()
        )
        checks = panel_checks(manifest)
        self.assertTrue(all(checks.values()), checks)
        self.assertGreaterEqual(len(manifest["panels"]["screen"]), 2)
        self.assertEqual("NOT_PERFORMED", manifest["kaggle_submission"])

    def test_sequence_precursor_sealed_gate_requires_live_economic_firing(self):
        run = {"rank": 1, "states": 720, "statuses": ["DONE", "DONE"],
               "invalid_actions": 0, "contract_violations": 0, "stderr": "", "seconds": 1.0}
        candidate = {**run, "precursor": {"firings": 0, "economic_reached": 0}}
        window = {"summary": {
            "mean_rank_improvement": 0, "mean_reward_delta": 0,
            "lower_tail_reward_delta": 0, "worst_reward_delta": 0,
            "mean_margin_delta": 0, "lower_tail_margin_delta": 0,
            "worst_margin_delta": 0, "precursor_firings": 0,
            "economic_reached": 0, "invalid_actions": 0, "contract_violations": 0,
        }, "raw_rows": [{"identity": {"episode_id": "screen"},
                           "champion": run, "candidate": candidate}]}
        passed, reasons, runtime = precursor_sealed_gate(
            window, {"rank": 0, "reward": 0, "margin": 0}, 2.0)
        self.assertFalse(passed)
        self.assertIn("precursor did not fire and reach its economic action in closed loop", reasons)
        self.assertFalse(any(runtime["primary_kpi_beyond_noise"].values()))

    def test_feed_economic_decision_is_independent_public_state_and_fires_both_seats(self):
        agent = load_agent(ROOT / "main.py")
        trace = feed_economic_trace(ROOT / "main.py")
        self.assertFalse(agent.FEED_ECONOMIC_DECISION)
        self.assertTrue(trace["both_seats"])
        self.assertTrue(trace["actual_intervention"])
        self.assertTrue(all(row["identity_seed_invariant"] for row in trace["rows"]))
        self.assertGreaterEqual(trace["firings"], 2)
        self.assertEqual("MIT", agent.PUBLIC_EXECUTION_SOURCES["feed_economic"]["license"])

    def test_feed_economic_decision_respects_cash_runway_and_current_herd(self):
        agent = load_agent(ROOT / "main.py")
        agent.FEED_ECONOMIC_DECISION = True
        obs = {"player": 0, "day": 8, "total_days": 30,
               "farms": [{"money": 250, "daily_operating_cost": 100}],
               "private": {"animals": {"COW": 2}, "shed": {}, "inventories": []},
               "market": {"prices": {"WHEAT": 25}}, "capabilities": ["BUY_PRODUCT"]}
        self.assertEqual([], agent._feed_economic_order(obs))
        obs["farms"][0]["money"] = 1000
        self.assertEqual([["BUY_PRODUCT", "WHEAT", 4]], agent._feed_economic_order(obs))
        obs["private"]["animals"] = {}
        self.assertEqual([], agent._feed_economic_order(obs))

    def test_decision_family_attribution_keeps_feed_land_and_labor_distinct(self):
        self.assertEqual("feed", decision_family(["FEED"]))
        self.assertEqual("feed", decision_family(["BUY_PRODUCT", "FEED", 2]))
        self.assertEqual("economic", decision_family(["BUY_ANIMAL", "COW", 1]))
        self.assertEqual("market", decision_family(["SELL", "MILK", 1]))
        self.assertEqual("land", decision_family(["BUY_LAND"]))
        self.assertEqual("labor", decision_family(["HIRE"]))

    def test_decision_family_measurement_is_leak_free_and_selects_screen_only(self):
        report = json.loads((ROOT / "docs/measurements/SOT-2832/"
                             "SOT-2832-decision-family-divergence.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual("economic", report["selected_family"])
        self.assertTrue(report["confirm"]["screen_selection_stable"])
        self.assertFalse(report["runtime_candidate_changed"])
        self.assertEqual("NOT_PERFORMED", report["kaggle_submission"])
        self.assertTrue(report["checks"]["private_future_not_in_features"])
        self.assertTrue(set(report["split"]["screen_entities"]).isdisjoint(
            report["split"]["confirm_entities"]))
        self.assertTrue(report["panels"]["screen"]["families"]["land"]["closed"])
        self.assertTrue(report["panels"]["screen"]["families"]["labor"]["closed"])

    def test_first_actions_uses_only_first_action_per_channel(self):
        actions = first_actions({"farmer": ["CARE", 1],
                                 "hands": [["FEED", 1], ["WATER", 2]],
                                 "market": [["BUY_PRODUCT", "FEED", 2], ["HIRE"]]})
        self.assertEqual(["CARE", 1], actions["farmer"])
        self.assertEqual(["FEED", 1], actions["hands"])
        self.assertEqual(["BUY_PRODUCT", "FEED", 2], actions["market"])

    def test_compact_sealed_gate_uses_only_untouched_confirm_identities(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/public_closed_loop_holdout.json").read_text()
        )
        screen = manifest["panels"]["screen"]
        confirm = manifest["panels"]["confirm"]
        self.assertTrue({row["opponent"] for row in screen}.isdisjoint(
            row["opponent"] for row in confirm
        ))
        self.assertTrue({row["seed"] for row in screen}.isdisjoint(
            row["seed"] for row in confirm
        ))

    def test_compact_sealed_gate_fails_closed_without_manifest_integrity(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/public_closed_loop_holdout.json").read_text()
        )
        manifest["manifest_sha256"] = "0" * 64
        report = measure_compact_sealed_gate(ROOT / "main.py", manifest)
        self.assertEqual("inconclusive", report["decision"])
        self.assertFalse(report["passed"])
        self.assertFalse(report["manifest_checks"]["manifest_digest"])

    def test_compact_sealed_gate_requires_reward_non_regression(self):
        from scripts.measure_compact_policy_sealed_gate import _sealed_gate

        window = {
            "summary": {
                "mean_margin_delta": 5, "lower_tail_margin_delta": 1,
                "worst_margin_delta": 1, "mean_reward_delta": -1,
                "candidate_mean_rank": 1,
            },
            "raw_rows": [{
                "identity": {"seed": 1},
                "champion": {"rank": 1, "states": 720, "statuses": ["DONE", "DONE"],
                             "invalid_actions": 0, "contract_violations": 0, "stderr": ""},
                "candidate": {"rank": 1, "states": 720, "statuses": ["DONE", "DONE"],
                              "invalid_actions": 0, "contract_violations": 0, "stderr": ""},
            }],
        }
        passed, reasons = _sealed_gate(window)
        self.assertFalse(passed)
        self.assertIn("mean reward regressed", reasons)

    def test_compact_replay_policy_constants_reproduce_from_screen_only(self):
        recorded = json.loads((ROOT / "docs/measurements/SOT-2823/"
                               "SOT-2826-compact-replay-distillation.json").read_text())
        agent = load_agent(ROOT / "main.py")
        self.assertEqual("screen", recorded["fit_split"])
        self.assertEqual(0, recorded["confirm_rows_used_for_tuning"])
        self.assertEqual(
            tuple(recorded["constants"]["hands_per_unlocked_quadrant"]),
            agent.COMPACT_REPLAY_POLICY_CONSTANTS["hands_per_unlocked_quadrant"],
        )
        self.assertEqual(
            tuple(tuple(row) for row in recorded["constants"]["land_milestones"]),
            agent.COMPACT_REPLAY_POLICY_CONSTANTS["land_milestones"],
        )
        dataset = ROOT / ".ai-jobs/sot2826-teacher.jsonl"
        if not dataset.exists():
            return
        report = distill_compact_policy(dataset)
        self.assertEqual(recorded, json.loads(json.dumps(report)))

    def test_compact_replay_policy_is_independent_and_all_branches_fire(self):
        agent = load_agent(ROOT / "main.py")
        self.assertFalse(agent.COMPACT_REPLAY_POLICY)
        self.assertFalse(agent.CASH_RUNWAY_ACREAGE_EXPANSION)
        self.assertFalse(agent.PRODUCTIVE_ACTION_CAPACITY)
        trace = compact_targeted_trace(ROOT / "main.py")
        self.assertTrue(trace["all_branches_fired"])
        self.assertGreater(trace["firings"]["land"], 0)
        self.assertGreater(trace["firings"]["labor"], 0)

    def test_replay_teacher_manifest_is_current_top_hash_pinned_and_isolated(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/replay_teacher_manifest.json").read_text()
        )
        checks = validate_teacher_manifest(manifest)
        self.assertTrue(all(checks.values()), checks)
        self.assertEqual(6, len(manifest["entries"]))
        self.assertEqual(
            {0, 1}, {row["winner_seat"] for row in manifest["entries"]}
        )
        self.assertEqual("NOT_PERFORMED", manifest["kaggle_submission"])

    def test_replay_teacher_manifest_rejects_split_and_digest_drift(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/replay_teacher_manifest.json").read_text()
        )
        manifest["entries"][3]["winner_team_id"] = manifest["entries"][0]["winner_team_id"]
        checks = validate_teacher_manifest(manifest)
        self.assertFalse(checks["manifest_digest"])
        self.assertFalse(checks["entity_holdout"])

    def test_teacher_projection_removes_private_future_and_credentials(self):
        observation = {
            "step": 4, "day": 1, "market": {"prices": {"WHEAT": 20}},
            "farms": [{"money": 100}], "private": {"shed": {"WHEAT": 99}},
            "future_prices": [999], "credentialToken": "never-emit",
            "remainingOverageTime": 12.5,
        }
        projected = public_projection(observation, 4)
        self.assertEqual(
            {"step": 4, "day": 1, "market": {"prices": {"WHEAT": 20}},
             "farms": [{"money": 100}]}, projected
        )
        with self.assertRaises(ValueError):
            public_projection(observation, 5)

    def test_shop_prefix_closed_loop_gate_requires_tail_and_runtime_integrity(self):
        from scripts.measure_shop_prefix_closed_loop import _gate

        healthy = {
            "summary": {"mean_margin_delta": 1, "lower_tail_margin_delta": 0,
                        "worst_margin_delta": 0, "candidate_mean_rank": 1.5},
            "raw_rows": [{"identity": {"seed": 1}, "champion": {
                "states": 720, "statuses": ["DONE", "DONE"], "invalid_actions": 0,
                "contract_violations": 0, "stderr": ""}, "candidate": {
                "states": 720, "statuses": ["DONE", "DONE"], "invalid_actions": 0,
                "contract_violations": 0, "stderr": ""}}],
        }
        self.assertEqual((True, []), _gate(healthy, True))
        healthy["summary"]["worst_margin_delta"] = -1
        passed, reasons = _gate(healthy, True)
        self.assertFalse(passed)
        self.assertIn("worst_margin_delta regressed", reasons)

    def test_shop_prefix_closed_loop_summary_preserves_direct_ablation_delta(self):
        from scripts.measure_shop_prefix_closed_loop import _summary

        rows = [{"candidate": {"rank": rank, "margin": margin},
                 "candidate_delta": {"reward": reward, "margin": margin}}
                for rank, reward, margin in ((1, 5, 10), (2, -2, -4), (1, 3, 6), (1, 0, 0))]
        summary = _summary(rows)
        self.assertEqual(-4, summary["worst_margin_delta"])
        self.assertEqual(-4, summary["lower_tail_margin_delta"])
        self.assertEqual(1.25, summary["candidate_mean_rank"])

    def test_shop_prefix_selector_uses_only_public_prefix_and_logs_every_branch(self):
        agent = load_agent(ROOT / "main.py")
        cases = {
            "yarn_first": ["YARN_STORE", "PIZZA_SHOP"],
            "yarn_second": ["PIZZA_SHOP", "YARN_STORE"],
            "yarn_third": ["PIZZA_SHOP", "BAKERY", "YARN_STORE"],
            "early_milk_support": ["BAKERY", "SMOOTHIE_SHOP"],
            "default": ["BAKERY", "JUICE_SHOP", "CAFE"],
        }
        for label, shops in cases.items():
            obs = {"town": {"unlocked_shops": (shops + ["CAFE"] * 3)[:3]
                             + ["YARN_STORE"]},
                   "private": {"identity": label, "seed": 1},
                   "episode_id": label, "submission_id": label, "seed": 1}
            before = agent.PUBLIC_SHOP_PREFIX_ROUTE_FIRES[label]
            selected, route = agent._public_shop_prefix_route(obs, record=True)
            self.assertEqual(label, selected)
            self.assertEqual(before + 1, agent.PUBLIC_SHOP_PREFIX_ROUTE_FIRES[label])
            self.assertIn(route["crop"], {"WHEAT", "STRAWBERRY"})
            mutated = json.loads(json.dumps(obs))
            mutated["private"] = {"identity": "changed", "seed": 999}
            mutated.update({"episode_id": "changed", "submission_id": "changed", "seed": 999})
            self.assertEqual((selected, route), agent._public_shop_prefix_route(mutated))

    def test_shop_prefix_route_normalizes_livestock_to_cash_feasible_orders(self):
        agent = load_agent(ROOT / "main.py")
        obs = {"player": 0, "day": 3, "total_days": 30,
               "farms": [{"money": 650, "farmer": [0, 0], "hands": [],
                           "tiles": [[None]], "daily_operating_cost": 100}],
               "private": {"animals": {}, "shed": {}, "seeds": {}, "inventories": [{}]},
               "market": {"prices": {"FEED": 20, "MILK": 100, "WOOL": 100}},
               "animals": {"COW": {"price": 500}, "SHEEP": {"price": 400}},
               "capabilities": ["BUY_ANIMAL"]}
        _, route = agent._public_shop_prefix_route(
            {"town": {"unlocked_shops": ["YARN_STORE"]}})
        self.assertEqual([], agent._care_livestock_orders(obs, route))
        obs["farms"][0]["money"] = 2400
        orders = agent._care_livestock_orders(obs, route)
        self.assertEqual(1, sum(order[0] == "BUY_ANIMAL" for order in orders))
        self.assertEqual("SHEEP", next(order[1] for order in orders
                                      if order[0] == "BUY_ANIMAL"))

    def test_public_closed_loop_manifest_is_pinned_isolated_and_leak_free(self):
        path = ROOT / "tests/fixtures/public_closed_loop_holdout.json"
        manifest = json.loads(path.read_text())
        checks = validate_closed_loop_manifest(manifest)
        self.assertTrue(all(checks.values()), checks)
        self.assertEqual("live-closed-loop", manifest["evidence_policy"]["mode"])
        self.assertEqual("open-loop-stress-only",
                         manifest["evidence_policy"]["recorded_action_replay"])
        self.assertFalse(manifest["evidence_policy"]["live_win_probability_claimed"])

    def test_public_closed_loop_manifest_fails_closed_on_drift_and_leakage(self):
        path = ROOT / "tests/fixtures/public_closed_loop_holdout.json"
        manifest = json.loads(path.read_text())
        manifest["artifacts"][0]["sha256"] = "0" * 64
        manifest["credentials"] = "must-never-be-committed"
        manifest["panels"]["confirm"][0]["seed"] = manifest["panels"]["screen"][0]["seed"]
        checks = validate_closed_loop_manifest(manifest)
        self.assertFalse(checks["manifest_digest"])
        self.assertFalse(checks["seed_holdout"])
        self.assertFalse(checks["no_sensitive_or_replay_payload_fields"])

    def test_productive_capacity_is_public_only_bounded_and_independent(self):
        agent = load_agent(ROOT / "main.py")
        trace = capacity_trace(agent)
        self.assertTrue(trace["private_invariant"])
        self.assertGreaterEqual(trace["capacity"]["acreage_limit"], 2)
        self.assertFalse(agent.PRODUCTIVE_ACTION_CAPACITY)
        self.assertFalse(agent.LONG_HORIZON_MIXED_FARM_ROUTE)
        self.assertEqual("MIT", agent.PUBLIC_EXECUTION_SOURCES["productive_action_capacity"]["license"])

    def test_productive_capacity_gate_rejects_no_action_improvement(self):
        summary = {"mean_rank": 1, "lower_tail_margin": 1, "worst_margin": 1}
        baseline = {window: {"summary": dict(summary)} for window in ("screen", "confirm")}
        baseline.update({"action_metrics": {"productive": 10}, "invalid_actions": 0,
                         "contract_violations": 0})
        candidate = json.loads(json.dumps(baseline))
        candidate["action_metrics"]["component_firings"] = 1
        paired = {window: {"checks": {"same_seed_direct_ab": True, "both_seats": True,
                                      "paired_non_regression": True}}
                  for window in ("screen", "confirm")}
        passed, reasons = capacity_gate(
            baseline, candidate, paired, 1.0, {"private_invariant": True})
        self.assertFalse(passed)
        self.assertIn("WATER/HARVEST/FERTILIZE total did not improve", reasons)

    def test_runway_expansion_is_independent_reserve_bounded_and_fires(self):
        agent = load_agent(ROOT / "main.py")
        rows = _targeted_trace(agent, True)
        self.assertEqual({0, 1}, {row["seat"] for row in rows})
        self.assertTrue(any(row["land"] for row in rows))
        self.assertTrue(any(row["hire"] for row in rows))
        self.assertTrue(any(row["plant"] for row in rows))
        self.assertTrue(any(row["water"] for row in rows))
        agent.CASH_RUNWAY_ACREAGE_EXPANSION = True
        plan = agent._runway_expansion_plan({
            "player": 0, "day": 5, "total_days": 30, "capabilities": ["BUY_LAND"],
            "land_costs": [1000],
            "farms": [{"money": 1100, "hands": [], "daily_operating_cost": 100,
                       "unlocked_quadrants": ["NW"], "tiles": [[None] * 6]}],
            "private": {"animals": {}}, "market": {"prices": {"FEED": 20}},
        }, {"seed_price": 10, "maturity_days": 2}, "WHEAT", 5)
        agent.CASH_RUNWAY_ACREAGE_EXPANSION = False
        self.assertEqual([], plan["land"])
        self.assertGreaterEqual(plan["reserve"], 300)
        self.assertFalse(agent.CASH_RUNWAY_ACREAGE_EXPANSION)
        self.assertFalse(agent.LONG_HORIZON_MIXED_FARM_ROUTE)
        self.assertEqual("MIT", agent.PUBLIC_EXECUTION_SOURCES["runway_acreage"]["license"])

    def test_runway_gate_rejects_non_improving_candidate(self):
        summary = {"mean_rank": 1, "lower_tail_margin": 1, "worst_margin": 1}
        base = {window: {"summary": dict(summary)} for window in ("screen", "confirm")}
        base["cash"] = {"mean_day_10_cash": 10, "mean_terminal_cash": 20,
                        "invalid_actions": 0, "contract_violations": 0}
        candidate = json.loads(json.dumps(base))
        candidate["component_firings"] = {"cash_runway_acreage": 1}
        paired = {window: {"checks": {"both_seats": True}} for window in ("screen", "confirm")}
        targeted = [{"land": 1, "hire": 1, "plant": 1, "water": 1}]
        passed, reasons = runway_gate(base, candidate, paired, 1.0, targeted)
        self.assertFalse(passed)
        self.assertIn("neither day-10 nor terminal cash improved", reasons)

    def test_post_repair_cash_flow_is_deterministic_isolated_and_auditable(self):
        manifest = json.loads((ROOT / "tests/fixtures/public_opponents.json").read_text())
        corpus = json.loads((ROOT / "tests/fixtures/replay_corpus_manifest.json").read_text())
        first = measure_post_repair_cash_flow(ROOT / "main.py", FIXTURE, manifest, corpus)
        second = measure_post_repair_cash_flow(ROOT / "main.py", FIXTURE, manifest, corpus)
        self.assertEqual(first, second)
        self.assertTrue(first["passed"], first)
        self.assertTrue(first["isolation"]["passed"])
        self.assertTrue(all(first["corpus_checks"].values()))
        self.assertEqual("fallback-public-artifacts", first["provenance"]["acquisition"]["status"])
        self.assertTrue(all(row["submission_id"] is None and row["episode_id"] is None
                            for row in first["provenance"]["entries"]))
        for window in ("screen", "confirm"):
            identities = [row["identity"] for row in first[window]["episodes"]]
            self.assertEqual({0, 1}, {row["seat"] for row in identities})
            self.assertTrue(first[window]["daily_mean"])
        self.assertIn("acreage_expansion", first["downstream_baselines_and_thresholds"])
        self.assertIn("productive_action_capacity", first["downstream_baselines_and_thresholds"])
        self.assertEqual("NOT_PERFORMED", first["kaggle_submission"])

    def test_care_livestock_is_independent_bounded_and_fires_both_seats(self):
        fixture = json.loads((ROOT / "tests/fixtures/care_livestock.json").read_text())
        policy = load_care_policy(ROOT / "main.py")
        episodes = evaluate_care(policy, fixture["screen"], True)
        self.assertEqual({0, 1}, {row["seat"] for row in episodes})
        self.assertTrue(all(row["care_action"] == ["CARE"] for row in episodes))
        self.assertTrue(all(any(order[0] == "BUY_ANIMAL" for order in row["market"])
                            for row in episodes))
        self.assertTrue(all(any(order[:2] == ["BUY_PRODUCT", "FEED"] for order in row["market"])
                            for row in episodes))
        self.assertTrue(all(any(order[0] == "SELL" and order[1] in {"MILK", "WOOL"}
                            for order in row["market"]) for row in episodes))
        self.assertTrue(all(row["net_margin"] > 0 for row in episodes))
        self.assertFalse(policy.LONG_HORIZON_MIXED_FARM_ROUTE)
        self.assertEqual("MIT", policy.PUBLIC_EXECUTION_SOURCES["care_livestock"]["license"])

    def test_care_livestock_rejects_unprofitable_or_runway_breaching_buy(self):
        policy = load_care_policy(ROOT / "main.py")
        obs = {"player": 0, "day": 25, "total_days": 30,
               "farms": [{"money": 550, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
               "private": {"animals": {}, "shed": {}, "seeds": {"WHEAT": 0}, "inventories": [{}]},
               "market": {"prices": {"WHEAT": 25, "FEED": 20, "MILK": 30}},
               "animals": {"COW": {"price": 500, "care_interval_days": 2,
                                     "product_per_care": 1, "feed_per_care": 1}},
               "capabilities": ["BUY_ANIMAL", "BUY_PRODUCT"]}
        self.assertFalse(any(order[0] == "BUY_ANIMAL" for order in policy.agent(obs)["market"]))

    def test_agent_is_last_callable_for_kaggle_file_loader(self):
        namespace = runpy.run_path(str(ROOT / "main.py"))
        callables = [name for name, value in namespace.items() if callable(value)]
        self.assertEqual("agent", callables[-1])

    def test_fresh_live_lb_reanchor_is_deterministic_and_leak_free(self):
        manifest = json.loads((ROOT / "tests/fixtures/live_lb_reanchor_manifest.json").read_text())
        replay_dir = ROOT / "docs/measurements/SOT-2785/replays"
        first = measure_live_lb_reanchor(manifest, replay_dir)
        self.assertEqual(first, measure_live_lb_reanchor(manifest, replay_dir))
        self.assertEqual("promoted", first["result"])
        self.assertTrue(all(first["checks"].values()))
        self.assertEqual({0, 1}, {first["screen"][side]["seat"] for side in ("candidate", "opponent")})
        self.assertEqual({0, 1}, {first["confirm"][side]["seat"] for side in ("candidate", "opponent")})
        self.assertTrue(first["transfer"]["candidate_stalled_both_windows"])
        self.assertEqual(0, first["screen"]["candidate"]["productive_actions"])
        self.assertEqual(0, first["confirm"]["candidate"]["fertilizer_component_firings"])
        self.assertEqual("NOT_PERFORMED", first["kaggle_submission"])

    def test_fertilizer_trace_distinguishes_action_from_supply_bottleneck(self):
        action_bound = classify_bottleneck({"fertilizer_demand": 132, "stock_available": 132,
                                            "fertilize_actions": 0,
                                            "collect_fertilizer_actions": 0})
        self.assertEqual("action-bound", action_bound["verdict"])
        self.assertEqual(132, action_bound["missing_actions"])
        supply_bound = classify_bottleneck({"fertilizer_demand": 132, "stock_available": 40,
                                            "fertilize_actions": 40,
                                            "collect_fertilizer_actions": 0})
        self.assertEqual("supply-bound", supply_bound["verdict"])
        self.assertEqual(92, supply_bound["missing_supply"])

    def test_fertilizer_coverage_uses_stock_without_market_buy(self):
        agent = load_agent(ROOT / "main.py")
        plant = {"kind": "PLANT", "crop": "STRAWBERRY", "planted_day": 1,
                 "watered_today": False, "yield_units": 0, "fertilized_until_day": -1}
        obs = {
            "player": 0, "step": 48, "day": 2, "hour": 0, "turns_per_day": 24,
            "total_days": 30,
            "farms": [{"money": 1000, "farmer": [0, 0], "hands": [], "tiles": [[plant]]}],
            "private": {"seeds": {"STRAWBERRY": 0}, "shed": {},
                        "inventories": [{"FERTILIZER": 1}]},
            "crops": {"STRAWBERRY": {"seed_price": 25, "maturity_days": 3,
                        "expected_yield": 3, "fallback_price": 50}},
            "market": {"prices": {"STRAWBERRY": 50}, "inventory": {"STRAWBERRY": 10000}},
        }
        result = agent.agent(obs)
        self.assertEqual(["FERTILIZE"], result["farmer"])
        self.assertFalse(any(order[:2] == ["BUY_PRODUCT", "FERTILIZER"]
                             for order in result["market"]))

    def test_strawberry_renewal_staggers_cohort_and_respects_horizon_capacity(self):
        agent = load_agent(ROOT / "main.py")
        plants = [
            {"kind": "PLANT", "crop": "STRAWBERRY", "planted_day": planted,
             "max_lifespan_step": lifespan, "yield_units": 0}
            for planted, lifespan in ((18, 610), (19, 700), (20, 720), (20, 730))
        ]
        obs = {"player": 0, "step": 600, "day": 25, "total_days": 30,
               "turns_per_day": 24,
               "farms": [{"farmer": [0, 0], "hands": [[1, 0], [2, 0]],
                           "tiles": [plants + [None]]}]}
        spec = {"first_yield_day": 2, "maturity_days": 3}
        before = agent.component_firing_counts()["staggered_strawberry_renewal"]
        # The imminent expiry opens a bounded three-worker replacement slice,
        # rather than allowing all eight seeds to recreate a single wave.
        self.assertEqual(3, agent._staggered_strawberry_seed_budget(obs, spec, 8, 9))
        self.assertEqual(before + 1,
                         agent.component_firing_counts()["staggered_strawberry_renewal"])
        self.assertEqual("MIT", agent.PUBLIC_EXECUTION_SOURCES["strawberry_renewal"]["license"])
        obs["day"] = 28
        obs["step"] = 672
        self.assertEqual(0, agent._staggered_strawberry_seed_budget(obs, spec, 8, 9))

    def test_strawberry_renewal_flag_is_independent(self):
        agent = load_agent(ROOT / "main.py")
        agent.STAGGERED_STRAWBERRY_RENEWAL = False
        obs = {"player": 0, "day": 29, "total_days": 30,
               "farms": [{"farmer": [0, 0], "hands": [], "tiles": [[None]]}]}
        self.assertEqual(7, agent._staggered_strawberry_seed_budget(
            obs, {"maturity_days": 3}, 7, 0))

    def test_authenticated_replay_manifest_is_hash_pinned_and_leak_free(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/authenticated_replay_manifest.json").read_text()
        )
        result = validate_authenticated_replay_cv(
            manifest, ROOT / "docs/measurements/SOT-2781/replays"
        )
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(result["checks"].values()), result["checks"])
        self.assertEqual("NOT_PERFORMED", result["kaggle_submission"])
        self.assertEqual({0, 1}, {row["seat"] for row in result["panels"]["screen"]})
        self.assertEqual({0, 1}, {row["seat"] for row in result["panels"]["confirm"]})
        self.assertLess(
            max(row["time_utc"] for row in result["panels"]["screen"]),
            min(row["time_utc"] for row in result["panels"]["confirm"]),
        )
        self.assertNotEqual(
            {row["entity_id"] for row in result["panels"]["screen"]},
            {row["entity_id"] for row in result["panels"]["confirm"]},
        )
        boundary = result["information_boundary"]["candidate_inputs"]
        self.assertIn("private and future fields excluded", boundary)
        self.assertIn("fallback-public-artifacts", result["fallback_boundary"])

    def test_authenticated_replay_manifest_rejects_hash_and_temporal_drift(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/authenticated_replay_manifest.json").read_text()
        )
        manifest["entries"][0]["time_utc"] = "2099-01-01T00:00:00Z"
        result = validate_authenticated_replay_cv(
            manifest, ROOT / "docs/measurements/SOT-2781/replays"
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["manifest_digest"])
        self.assertFalse(result["checks"]["confirm_after_screen"])

    def test_demand_premium_gate_requires_strict_improvement(self):
        summary = {"lower_tail_margin": 1, "worst_margin": 1,
                   "mean_margin": 1, "mean_rank": 1}
        report = {window: {"summary": dict(summary)} for window in ("screen", "confirm")}
        passed, reasons = demand_premium_gate(report, json.loads(json.dumps(report)))
        self.assertFalse(passed)
        self.assertIn("no strict rank, margin, or tail improvement", reasons)

    def test_public_opponent_manifest_is_pinned_and_maps_to_cv_entities(self):
        manifest = json.loads((ROOT / "tests/fixtures/public_opponents.json").read_text())
        artifacts = {row["id"]: row for row in manifest["artifacts"]}
        entities = {row["opponent"] for window in ("screen", "confirm")
                    for row in FIXTURE["leak_free_cv"][window]}
        self.assertLessEqual(entities, set(artifacts))
        self.assertGreaterEqual(len({row["lineage"] for row in artifacts.values()}), 2)
        self.assertTrue(all(len(row["commit"]) == 40 and len(row["sha256"]) == 64
                            for row in artifacts.values()))
        self.assertTrue(all(raw_url(row).startswith("https://raw.githubusercontent.com/")
                            for row in artifacts.values()))

    def test_public_opponent_measurement_reports_opponent_rank_margin_tail(self):
        manifest = json.loads((ROOT / "tests/fixtures/public_opponents.json").read_text())
        corpus = json.loads((ROOT / "tests/fixtures/replay_corpus_manifest.json").read_text())
        with mock.patch("scripts.measure_leak_free_cv.fetch_artifacts") as fetch:
            fetch.return_value = {
                row["id"]: ROOT / "tests/fixtures/champion_sot_2263.py"
                for row in manifest["artifacts"]
            }
            result = measure(ROOT / "main.py", FIXTURE, manifest, corpus)
        self.assertTrue(result["passed"], result)
        self.assertEqual("NOT_PERFORMED", result["kaggle_submission"])
        for window in ("screen", "confirm"):
            self.assertEqual(4, result[window]["summary"]["episodes"])
            self.assertIn("mean_rank", result[window]["summary"])
            self.assertIn("mean_margin", result[window]["summary"])
            self.assertIn("lower_tail_margin", result[window]["summary"])
        self.assertTrue(all(result["corpus_checks"].values()), result["corpus_checks"])
        self.assertEqual("fallback-public-artifacts",
                         result["corpus_manifest"]["acquisition"]["status"])

    def test_replay_corpus_manifest_digest_identity_and_fallback_are_auditable(self):
        manifest = json.loads((ROOT / "tests/fixtures/public_opponents.json").read_text())
        artifacts = {row["id"]: row for row in manifest["artifacts"]}
        corpus = json.loads((ROOT / "tests/fixtures/replay_corpus_manifest.json").read_text())
        checks = validate_corpus_manifest(corpus, FIXTURE, artifacts)
        self.assertTrue(all(checks.values()), checks)
        unsigned = {key: value for key, value in corpus.items() if key != "manifest_sha256"}
        self.assertEqual(corpus["manifest_sha256"], canonical_sha256(unsigned))
        self.assertEqual({0, 1}, {row["recorded_seat"] for row in corpus["entries"]})
        self.assertTrue(all(row["submission_id"] is None and row["episode_id"] is None
                            and row["replay_sha256"] is None for row in corpus["entries"]))

    def test_replay_corpus_manifest_rejects_digest_and_identity_drift(self):
        manifest = json.loads((ROOT / "tests/fixtures/public_opponents.json").read_text())
        artifacts = {row["id"]: row for row in manifest["artifacts"]}
        corpus = json.loads((ROOT / "tests/fixtures/replay_corpus_manifest.json").read_text())
        corpus["entries"][0]["episode_id"] = 999
        checks = validate_corpus_manifest(corpus, FIXTURE, artifacts)
        self.assertFalse(checks["manifest_digest"])
        self.assertFalse(checks["authenticated_replay_not_claimed"])

    def test_cv_holdouts_isolate_entity_seed_episode_and_time(self):
        result = validate_cv_holdouts(FIXTURE["leak_free_cv"])
        self.assertTrue(result["passed"], result)
        self.assertTrue(set(result["episode_ids"]["screen"]).isdisjoint(result["episode_ids"]["confirm"]))

    def test_cv_holdout_rejects_reused_opponent_seed_and_future_window(self):
        bad = {
            "screen": [{"opponent": "same", "seed": 1, "time_index": 2}],
            "confirm": [{"opponent": "same", "seed": 1, "time_index": 1}],
        }
        result = validate_cv_holdouts(bad)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["opponent_holdout"])
        self.assertFalse(result["checks"]["seed_holdout"])
        self.assertFalse(result["checks"]["temporal_order"])

    def test_paired_cv_runs_same_seed_both_seats_with_tail_worst_and_rank(self):
        champion = load_agent(ROOT / "tests/fixtures/champion_sot_2263.py")
        candidate = load_agent(ROOT / "main.py")
        entities = FIXTURE["leak_free_cv"]["screen"][:1]
        first = evaluate_paired_cv(champion, candidate, FIXTURE, entities)
        second = evaluate_paired_cv(champion, candidate, FIXTURE, entities)
        self.assertEqual(first, second)
        self.assertEqual({0, 1}, {row["seat"] for row in first["episodes"]})
        self.assertEqual({entities[0]["seed"]}, {row["seed"] for row in first["episodes"]})
        self.assertEqual(2, first["summary"]["episode_count"])
        self.assertIn("lower_tail_reward_delta", first["summary"])
        self.assertIn("worst_reward_delta", first["summary"])
        self.assertIn("mean_candidate_rank", first["summary"])
        self.assertTrue(all(first["checks"].values()), first)

    def test_private_and_future_hints_do_not_enter_cv_identity(self):
        base = json.loads(json.dumps(FIXTURE["leak_free_cv"]))
        mutated = json.loads(json.dumps(base))
        mutated["screen"][0]["private"] = {"opponent_bank": 999999}
        mutated["screen"][0]["future_prices"] = [999999]
        self.assertTrue(validate_cv_holdouts(base)["passed"])
        result = validate_cv_holdouts(mutated)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["no_private_information"])
        self.assertFalse(result["checks"]["no_future_price_reference"])

    def test_scarcity_pressure_uses_public_state_and_is_opponent_order_invariant(self):
        agent = load_agent(ROOT / "main.py")
        obs = json.loads(json.dumps(FIXTURE["opponent_policy"]["screen"][0]["observation"]))
        expected = agent._scarcity_pressure(obs, "WHEAT")
        obs["farms"][1:] = reversed(obs["farms"][1:])
        obs["private"] = {"shed": {"SECRET": 999}, "seeds": {"WHEAT": 1}, "inventories": [[]]}
        self.assertEqual(expected, agent._scarcity_pressure(obs, "WHEAT"))
        self.assertTrue(all(0 <= value <= 1 for value in expected.values()))

    def test_scarcity_policy_handles_stock_hire_and_market_pressure_scenarios(self):
        agent = load_agent(ROOT / "main.py")
        screen = evaluate_opponent_policy(agent, FIXTURE["opponent_policy"]["screen"])
        confirm = evaluate_opponent_policy(agent, FIXTURE["opponent_policy"]["confirm"])
        self.assertTrue(screen["passed"], screen)
        self.assertTrue(confirm["passed"], confirm)

    def test_online_identification_is_public_bounded_and_deterministic(self):
        agent = load_agent(ROOT / "main.py")
        base = {
            "player": 0, "step": 0, "day": 0, "hour": 0,
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [],
                       "tiles": [[{"kind": "WEED"}]]}],
            "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[]]},
            "market": {"prices": {"WHEAT": 20}},
        }
        first = agent.agent(json.loads(json.dumps(base)))
        second = agent.agent(json.loads(json.dumps(base)))
        self.assertEqual(first, second)
        self.assertEqual(1, len(agent._PUBLIC_HISTORY))
        for step in range(1, agent.HISTORY_LIMIT + 8):
            obs = json.loads(json.dumps(base))
            obs["step"], obs["hour"] = step, step
            obs["market"]["prices"]["WHEAT"] = 20 + step % 3
            agent.agent(obs)
        self.assertEqual(agent.HISTORY_LIMIT, len(agent._PUBLIC_HISTORY))
        self.assertTrue(all(set(row) == {"step", "prices", "yields", "weeds",
                                         "workers", "backlog", "acreage"}
                            for row in agent._PUBLIC_HISTORY))
        self.assertTrue(all(set(row["backlog"]) == {"water", "harvest", "fertilize"}
                            for row in agent._PUBLIC_HISTORY))

    def test_uncertainty_set_and_cvar_proxy_react_to_observed_tail(self):
        agent = load_agent(ROOT / "main.py")
        spec = agent.DEFAULT_CROPS["WHEAT"]
        stable = ({"prices": {"WHEAT": 30}, "yields": {"WHEAT": 3}, "weeds": 0},)
        shifted = stable + ({"prices": {"WHEAT": 10}, "yields": {"WHEAT": 1}, "weeds": 3},)
        self.assertEqual(3, len(agent._uncertainty_scenarios("WHEAT", spec, shifted)))
        self.assertLess(agent._robust_crop_value("WHEAT", spec, 1, 30, shifted),
                        agent._robust_crop_value("WHEAT", spec, 1, 30, stable))

    def test_competitive_oracle_replays_multiple_farms_and_relative_rank(self):
        result = run_competitive_market(FIXTURE, FIXTURE["competitive_oracle"]["screen"][0])
        self.assertEqual(2, len(result["farms"]))
        self.assertEqual(sorted(result["ranks"]), [1, 2])
        self.assertEqual(result["scores"][0] - result["scores"][1], result["relative_score"])
        self.assertEqual(result["scores"].index(max(result["scores"])), result["winner"])

    def test_competitive_oracle_uses_shared_market_lockstep_quotes(self):
        result = run_competitive_market(FIXTURE, FIXTURE["competitive_oracle"]["screen"][0])
        simultaneous = next(row for row in result["trace"] if len(row["pre_commit_quotes"]) == 2)
        self.assertEqual(len(set(simultaneous["pre_commit_quotes"].values())), 1)
        self.assertNotEqual(10000, result["shared_market"]["inventory"]["WHEAT"])

    def test_competitive_oracle_keeps_private_stock_per_farm_and_shared_per_worker(self):
        scenario = FIXTURE["competitive_oracle"]["screen"][0]
        before = json.loads(json.dumps(scenario))
        result = run_competitive_market(FIXTURE, scenario)
        self.assertEqual(before, scenario)
        self.assertIn("seeds", result["farms"][0]["private"])
        self.assertIn("inventories", result["farms"][0]["private"])
        self.assertNotEqual(result["farms"][0]["private"]["shed"], result["farms"][1]["private"]["shed"])

    def test_bounded_rollout_is_deterministic_and_does_not_mutate_observation(self):
        rollout = FIXTURE["rollout"]
        observation = rollout["observation"]
        before = json.loads(json.dumps(observation))
        kwargs = {"horizon": rollout["horizon"], "crop_specs": FIXTURE["crops"],
                  "total_days": FIXTURE["days"], "turns_per_day": FIXTURE["turns_per_day"]}
        first = bounded_rollout(observation, rollout["candidate"], **kwargs)
        second = bounded_rollout(observation, rollout["candidate"], **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(before, observation)
        self.assertEqual(0, first["invalid_actions"])
        self.assertEqual(0, first["contract_violations"])

    def test_bounded_rollout_compares_sequences_under_the_same_screen(self):
        rollout = FIXTURE["rollout"]
        kwargs = {"horizon": rollout["horizon"], "crop_specs": FIXTURE["crops"],
                  "total_days": FIXTURE["days"], "turns_per_day": FIXTURE["turns_per_day"]}
        champion = bounded_rollout(rollout["observation"], rollout["champion"], **kwargs)
        candidate = bounded_rollout(rollout["observation"], rollout["candidate"], **kwargs)
        self.assertGreater(candidate["score"], champion["score"])
        self.assertEqual(champion["deadline_step"], candidate["deadline_step"])

    def test_bounded_rollout_uses_no_future_market_or_randomness(self):
        rollout = FIXTURE["rollout"]
        observation = json.loads(json.dumps(rollout["observation"]))
        observation["future_prices"] = {"WHEAT": [999999]}
        kwargs = {"horizon": 1, "crop_specs": FIXTURE["crops"],
                  "total_days": FIXTURE["days"], "turns_per_day": FIXTURE["turns_per_day"]}
        with_hint = bounded_rollout(observation, rollout["candidate"], **kwargs)
        observation.pop("future_prices")
        without_hint = bounded_rollout(observation, rollout["candidate"], **kwargs)
        self.assertEqual(with_hint, without_hint)

    def test_bounded_rollout_caps_horizon_at_deadline_and_detects_collision(self):
        rollout = FIXTURE["rollout"]
        observation = json.loads(json.dumps(rollout["observation"]))
        observation["step"] = FIXTURE["days"] * FIXTURE["turns_per_day"] - 1
        observation["farms"][0]["hands"] = [[2, 0]]
        observation["private"]["inventories"] = [{}, {}]
        actions = [{"farmer": ["EAST"], "hands": [["WEST"]], "market": []}] * 3
        result = bounded_rollout(observation, actions, horizon=3, crop_specs=FIXTURE["crops"],
                                 total_days=FIXTURE["days"], turns_per_day=FIXTURE["turns_per_day"])
        self.assertEqual(1, result["steps_simulated"])
        self.assertEqual(0, result["remaining_steps"])
        self.assertEqual(1, result["assignment_conflicts"])

    def test_fixed_seeds_are_reproducible(self):
        agent = load_agent(ROOT / "main.py")
        first = evaluate(agent, FIXTURE, FIXTURE["screen_seeds"])
        second = evaluate(agent, FIXTURE, FIXTURE["screen_seeds"])
        self.assertEqual(first, second)
        self.assertEqual(0, first["mean"]["invalid_actions"])

    def test_screen_and_confirm_use_independent_reproducible_seeds(self):
        self.assertTrue(set(FIXTURE["screen_seeds"]).isdisjoint(FIXTURE["confirm_seeds"]))
        screen_seeds = {seed for scenario in FIXTURE["screen_scenarios"] for seed in scenario["seeds"]}
        confirm_seeds = {seed for scenario in FIXTURE["confirm_scenarios"] for seed in scenario["seeds"]}
        self.assertTrue(screen_seeds.isdisjoint(confirm_seeds))
        self.assertTrue(set(s["name"] for s in FIXTURE["screen_scenarios"]).isdisjoint(
            s["name"] for s in FIXTURE["confirm_scenarios"]))
        agent = load_agent(ROOT / "main.py")
        self.assertEqual(
            evaluate(agent, FIXTURE, FIXTURE["confirm_seeds"]),
            evaluate(agent, FIXTURE, FIXTURE["confirm_seeds"]),
        )

    def test_invalid_action_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.py"
            path.write_text("def agent(obs):\n return {'farmer':['FLY'], 'hands':[], 'market':[]}\n")
            result = evaluate(load_agent(path), FIXTURE, [1])
        self.assertEqual(FIXTURE["days"] * FIXTURE["turns_per_day"], result["mean"]["invalid_actions"])
        self.assertLess(result["mean"]["leaderboard_proxy"], result["mean"]["final_assets"])

    def test_submission_contract_rejects_bad_arity_and_unknown_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad_contract.py"
            path.write_text("def agent(obs):\n return {'farmer':['PLANT','RICE'], 'hands':[], 'market':[['HIRE', 1]]}\n")
            result = run_episode(load_agent(path), FIXTURE, 1)
        self.assertGreater(result.contract_violations, 0)

    def test_runtime_observation_and_clock_match_public_contract(self):
        seen = []

        class Recorder:
            @staticmethod
            def agent(obs):
                seen.append(obs)
                return {"farmer": ["PASS"], "hands": [["PASS"] for _ in obs["farms"][0]["hands"]], "market": []}

        run_episode(Recorder, FIXTURE, 1)
        self.assertEqual(30 * 24, len(seen))
        self.assertEqual({"player", "step", "day", "hour", "total_days", "turns_per_day",
                          "shed_capacity", "farms", "private", "market", "town"}, set(seen[0]))
        self.assertEqual(10, len(seen[0]["farms"][0]["tiles"]))
        self.assertEqual("LOCKED", seen[0]["farms"][0]["tiles"][0][5])

    def test_harvest_is_carried_then_dropped_and_only_cash_is_rewarded(self):
        fixture = {**FIXTURE, "days": 3, "turns_per_day": 1, "initial_seeds": 1}

        class Farmer:
            @staticmethod
            def agent(obs):
                actions = {0: ["PLANT", "WHEAT"], 1: ["WATER"], 2: ["HARVEST"]}
                return {"farmer": actions[obs["day"]], "hands": [], "market": []}

        result = run_episode(Farmer, fixture, 1)
        self.assertEqual(1, result.harvested)
        self.assertEqual(fixture["initial_money"], result.reward)
        self.assertEqual(result.reward, result.final_assets)

    def test_two_unwatered_day_refreshes_turn_plant_into_weed(self):
        fixture = {**FIXTURE, "days": 3, "turns_per_day": 1, "initial_seeds": 1}
        observed = []

        class NeglectfulFarmer:
            @staticmethod
            def agent(obs):
                observed.append(obs["farms"][0]["tiles"][0][0])
                action = ["PLANT", "WHEAT"] if obs["day"] == 0 else ["PASS"]
                return {"farmer": action, "hands": [], "market": []}

        run_episode(NeglectfulFarmer, fixture, 1)
        self.assertEqual("WEED", observed[2]["kind"])

    def test_threshold_rejects_regression(self):
        champion = {"mean": {"final_assets": 100, "profit": 10, "cultivated": 2, "harvested": 2, "invalid_actions": 0}}
        candidate = {"mean": {"final_assets": 99, "profit": 10, "cultivated": 2, "harvested": 2, "invalid_actions": 0}}
        passed, reasons = compare(champion, candidate, FIXTURE["thresholds"])
        self.assertFalse(passed)
        self.assertIn("final_assets ratio", reasons[0])

    def test_distribution_gate_rejects_tail_or_worst_case_regression(self):
        champion = {"lower_quantile": {"final_assets": 100, "profit": 20},
                    "worst": {"final_assets": 90, "profit": 10, "invalid_actions": 0, "contract_violations": 0}}
        candidate = {"lower_quantile": {"final_assets": 99, "profit": 20},
                     "worst": {"final_assets": 90, "profit": 10, "invalid_actions": 1, "contract_violations": 0}}
        passed, reasons = compare_distribution(champion, candidate, FIXTURE["thresholds"])
        self.assertFalse(passed)
        self.assertTrue(any("lower_quantile final_assets" in reason for reason in reasons))
        self.assertIn("worst invalid_actions increased", reasons)

    def test_distribution_gate_requires_strict_tail_or_worst_improvement(self):
        metrics = {"final_assets": 100, "profit": 20, "invalid_actions": 0,
                   "contract_violations": 0}
        result = {"lower_quantile": dict(metrics), "worst": dict(metrics)}
        passed, reasons = compare_distribution(result, result, FIXTURE["thresholds"])
        self.assertFalse(passed)
        self.assertIn("no strict lower-tail or worst-case improvement", reasons)

    def test_distribution_scenarios_cover_requested_shift_dimensions(self):
        scenarios = FIXTURE["screen_scenarios"] + FIXTURE["confirm_scenarios"]
        overrides = [scenario["overrides"] for scenario in scenarios]
        self.assertTrue(any("prices" in value.get("crops", {}).get("WHEAT", {}) for value in overrides))
        self.assertTrue(any("CORN" in value.get("crops", {}) for value in overrides))
        self.assertTrue(any("board_size" in value for value in overrides))
        self.assertTrue(any("initial_weeds" in value for value in overrides))
        self.assertTrue(any("days" in value for value in overrides))
        self.assertTrue(any("initial_hands" in value for value in overrides))

    def test_scenario_evaluation_reports_lower_quantile_and_worst(self):
        result = evaluate_scenarios(load_agent(ROOT / "main.py"), FIXTURE, FIXTURE["screen_scenarios"])
        self.assertEqual([s["name"] for s in FIXTURE["screen_scenarios"]], result["scenario_names"])
        self.assertLessEqual(result["worst"]["final_assets"], result["lower_quantile"]["final_assets"])
        self.assertGreaterEqual(result["worst"]["invalid_actions"], result["mean"]["invalid_actions"])

    def test_zero_baseline_metric_does_not_divide_by_zero(self):
        champion = {"mean": {"final_assets": 0, "profit": 0, "cultivated": 0, "harvested": 0, "invalid_actions": 0}}
        candidate = {"mean": {"final_assets": 1, "profit": 1, "cultivated": 1, "harvested": 1, "invalid_actions": 0}}
        passed, reasons = compare(champion, candidate, FIXTURE["thresholds"])
        self.assertTrue(passed, reasons)

    def test_multi_worker_candidate_routes_without_invalid_actions(self):
        agent = load_agent(ROOT / "main.py")
        agent.MIN_HAND_TARGET = 3
        agent.MAX_HAND_TARGET = 3
        result = run_episode(agent, FIXTURE, 11)
        self.assertEqual(0, result.invalid_actions)
        self.assertGreater(result.cultivated, 1)
        self.assertGreater(result.harvested, 1)

    def test_worker_target_adapts_to_observed_land_and_remaining_harvests(self):
        agent = load_agent(ROOT / "main.py")
        small = {"tiles": [[None] * 4 for _ in range(4)]}
        wide = {"tiles": [[None] * 6 for _ in range(6)]}
        self.assertEqual(4, agent._hand_target(small, harvests_left=3))
        self.assertEqual(5, agent._hand_target(wide, harvests_left=3))
        self.assertEqual(0, agent._hand_target(wide, harvests_left=0))

    def test_worker_assignments_are_unique_and_respect_seed_count(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0,
            "day": 0,
            "hour": 3,
            "farms": [{
                "money": 100,
                "farmer": [0, 0],
                "hands": [[1, 0], [2, 0]],
                "hires_today": 2,
                "tiles": [[None, None, None], [None, None, None], [None, None, None]],
            }],
            "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[], [], []]},
        }
        result = agent.agent(obs)
        plant_actions = [action for action in [result["farmer"], *result["hands"]] if action[0] == "PLANT"]
        self.assertEqual(1, len(plant_actions))

    def test_global_assignment_does_not_let_planting_delay_harvest(self):
        agent = load_agent(ROOT / "main.py")
        tiles = [["LOCKED"] * 5 for _ in range(2)]
        tiles[0][1] = None
        tiles[0][3] = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
                       "watered_today": True, "yield_units": 3}
        obs = {"player": 0, "day": 3, "hour": 10,
               "farms": [{"money": 100, "farmer": [0, 0], "hands": [[4, 0]], "tiles": tiles}],
               "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[], []]}}
        result = agent.agent(obs)
        self.assertEqual(["EAST"], result["farmer"])
        self.assertEqual([["WEST"]], result["hands"])

    def test_global_assignment_avoids_duplicate_move_destinations(self):
        agent = load_agent(ROOT / "main.py")
        tiles = [["LOCKED"] * 3 for _ in range(3)]
        tiles[1][1] = {"kind": "WEED"}
        tiles[1][2] = {"kind": "WEED"}
        obs = {"player": 0, "day": 1, "hour": 2,
               "farms": [{"money": 100, "farmer": [0, 0], "hands": [[2, 0]], "tiles": tiles}],
               "private": {"shed": {}, "seeds": {}, "inventories": [[], []]}}
        result = agent.agent(obs)
        actions = [result["farmer"], *result["hands"]]
        offsets = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
        destinations = [(x + offsets[action[0]][0], y + offsets[action[0]][1])
                        for (x, y), action in zip(((0, 0), (2, 0)), actions)]
        self.assertEqual(len(destinations), len(set(destinations)))

    def test_public_scheduler_standing_work_fires_before_global_matching(self):
        agent = load_agent(ROOT / "main.py")
        agent.PUBLIC_SCHEDULER_COMPONENT = True
        tiles = [[None, {"kind": "WEED"}], ["LOCKED", "LOCKED"]]
        obs = {"player": 0, "day": 1, "hour": 2,
               "farms": [{"money": 100, "farmer": [0, 0], "hands": [[1, 0]], "tiles": tiles}],
               "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [{}, {}]}}
        before = agent.component_firing_counts()["public_scheduler"]
        result = agent.agent(obs)
        self.assertEqual(["DIG"], result["hands"][0])
        self.assertEqual(before + 1, agent.component_firing_counts()["public_scheduler"])
        self.assertEqual("MIT", agent.PUBLIC_EXECUTION_SOURCES["scheduler"]["license"])

    def test_sequence_precursor_policy_is_independent_bounded_and_auditable(self):
        agent = load_agent(ROOT / "main.py")
        self.assertFalse(agent.SEQUENCE_PRECURSOR_POLICY)
        tiles = [["LOCKED" for _ in range(3)] for _ in range(3)]
        tiles[1][1] = {"kind": "PASTURE"}
        tiles[1][2] = None
        farm = {"money": 750, "farmer": [2, 1], "hands": [], "tiles": tiles}
        obs = {"player": 0, "step": 1, "day": 0, "hour": 1, "turns_per_day": 24,
               "total_days": 30, "farms": [farm],
               "private": {"shed": {"SECRET": 99}, "seeds": {}, "inventories": [{}]},
               "market": {"prices": {}, "inventory": {"WHEAT": 17}},
               "town": {"unlocked_shops": []}}
        baseline = agent.agent(obs)
        self.assertNotEqual(["BUILD_PASTURE"], baseline["farmer"])

        candidate = load_agent(ROOT / "main.py")
        candidate.SEQUENCE_PRECURSOR_POLICY = True
        action = candidate.agent(obs)
        evidence = candidate.component_firing_counts()["sequence_precursor_policy"]
        self.assertEqual(["BUILD_PASTURE"], action["farmer"])
        self.assertEqual({"firings": 1, "economic_reached": 1, "phase": "economic_reached"}, evidence)
        self.assertEqual((("WHEAT", 17),), candidate._SEQUENCE_PRECURSOR_STATE["public_inventory"])
        self.assertIn("no action trace", candidate.PUBLIC_EXECUTION_SOURCES["sequence_precursor"]["boundary"])

    def test_sequence_precursor_policy_expires_without_relaxing_economic_thresholds(self):
        agent = load_agent(ROOT / "main.py")
        agent.SEQUENCE_PRECURSOR_POLICY = True
        tiles = [["LOCKED", "LOCKED"], ["LOCKED", {"kind": "PASTURE"}]]
        obs = {"player": 0, "step": 30, "day": 1, "hour": 6, "turns_per_day": 24,
               "farms": [{"money": 50000, "farmer": [0, 0], "hands": [], "tiles": tiles}],
               "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
               "market": {"prices": {}, "inventory": {}}, "town": {"unlocked_shops": []}}
        action = agent.agent(obs)
        self.assertNotEqual(["BUILD_PASTURE"], action["farmer"])
        self.assertFalse(agent.FEED_ECONOMIC_DECISION)
        self.assertFalse(agent.LONG_HORIZON_MIXED_FARM_ROUTE)
        self.assertFalse(agent.CASH_RUNWAY_ACREAGE_EXPANSION)
        self.assertFalse(agent.PRODUCTIVE_ACTION_CAPACITY)

    def test_multi_stop_bundle_is_independent_bounded_and_fires(self):
        agent = load_agent(ROOT / "main.py")
        agent.PUBLIC_SCHEDULER_COMPONENT = True
        agent.MULTI_STOP_TASK_BUNDLING = True
        tiles = [[None for _ in range(4)] for _ in range(4)]
        tiles[0][0] = tiles[3][3] = "LOCKED"
        me = {"farmer": [0, 0], "hands": [[3, 3]], "tiles": tiles}
        before = agent.component_firing_counts()["multi_stop_task_bundling"]
        actions = agent._plan_workers(me, 0, 8, "WHEAT", agent.DEFAULT_CROPS)
        self.assertEqual(2, len(actions))
        self.assertEqual(before + 1, agent.component_firing_counts()["multi_stop_task_bundling"])
        self.assertEqual("MIT", agent.PUBLIC_EXECUTION_SOURCES["task_bundling"]["license"])

        agent.MULTI_STOP_TASK_BUNDLING = False
        agent._plan_workers(me, 0, 8, "WHEAT", agent.DEFAULT_CROPS)
        self.assertEqual(before + 1, agent.component_firing_counts()["multi_stop_task_bundling"])

    def test_projected_market_clips_and_orders_same_turn_drop_sales(self):
        agent = load_agent(ROOT / "main.py")
        private = {"shed": {"WHEAT": 1}, "inventories": [{"WHEAT": 2, "CORN": 3}]}
        self.assertEqual({"WHEAT": 3, "CORN": 3},
                         agent._projected_shed_inventory(private, [["DROP"]]))
        obs = {"player": 0,
               "farms": [{}, {"tiles": [[{"kind": "PLANT", "crop": "CORN", "yield_units": 4}]]}],
               "market": {"inventory": {"CORN": 120, "WHEAT": 90},
                          "inventory_anchor": {"CORN": 100, "WHEAT": 100}}}
        ordered = sorted(("WHEAT", "CORN"), key=lambda crop: agent._sale_priority(obs, crop))
        self.assertEqual(["CORN", "WHEAT"], ordered)

    def test_shed_overflow_policy_sells_only_required_room_and_drops_carried_goods(self):
        agent = load_agent(ROOT / "main.py")
        agent.SHED_OVERFLOW_PROTECTION = True
        obs = {
            "player": 0, "day": 4, "hour": 2, "turns_per_day": 3,
            "shed_capacity": 10,
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [[1, 0]],
                       "tiles": [["LOCKED", "LOCKED"]]}],
            "private": {"shed": {"WHEAT": 8}, "seeds": {},
                        "inventories": [{"WHEAT": 3}, {"WHEAT": 1}]},
            "market": {"prices": {"WHEAT": 5}},
        }
        before = agent.component_firing_counts()["shed_overflow"]
        actions, orders = agent._protect_shed_capacity(obs, [["FERTILIZE"], ["PASS"]], agent.DEFAULT_CROPS)
        self.assertEqual([["FERTILIZE"], ["DROP"]], actions)
        self.assertEqual([["SELL", "WHEAT", 2]], orders)
        self.assertGreater(agent.component_firing_counts()["shed_overflow"], before)
        self.assertFalse(agent.PROJECTED_MARKET_EXECUTION)

    def test_overflow_fixture_records_discarded_units(self):
        fixture = {**FIXTURE, "days": 4, "turns_per_day": 3, "shed_capacity": 2,
                   "initial_hands": 2, "initial_seeds": 12}
        baseline = load_agent(ROOT / "main.py")
        baseline.SHED_OVERFLOW_PROTECTION = False
        candidate = load_agent(ROOT / "main.py")
        candidate.SHED_OVERFLOW_PROTECTION = True
        old = run_episode(baseline, fixture, 17)
        new = run_episode(candidate, fixture, 17)
        self.assertGreaterEqual(old.discarded_units, new.discarded_units)
        self.assertEqual(0, new.invalid_actions)

    def test_movement_stays_within_board_at_boundary(self):
        agent = load_agent(ROOT / "main.py")
        tiles = [["LOCKED" for _ in range(3)] for _ in range(3)]
        tiles[0][0] = None
        obs = {
            "player": 0, "day": 0,
            "farms": [{"money": 100, "farmer": [2, 2], "hands": [], "hires_today": 0, "tiles": tiles}],
            "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[]]},
        }
        self.assertIn(agent.agent(obs)["farmer"][0], {"NORTH", "WEST"})

    def test_missing_market_keys_and_unknown_inventory_are_safe(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 1,
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
            "private": {"shed": {"UNKNOWN": 3}, "seeds": {}, "inventories": [[]]},
        }
        result = agent.agent(obs)
        self.assertEqual({"farmer", "hands", "market"}, set(result))

    def test_mixed_farm_route_is_independent_and_uses_public_horizon(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 14, "total_days": 30,
            "crops": {
                "WHEAT": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3, "fallback_price": 15},
                "MELON": {"seed_price": 40, "maturity_days": 5, "expected_yield": 2, "fallback_price": 80},
                "STRAWBERRY": {"seed_price": 25, "maturity_days": 3, "expected_yield": 3, "fallback_price": 50},
            },
            "market": {"prices": {"WHEAT": 15, "MELON": 80, "STRAWBERRY": 50}},
            "farms": [{"money": 2000, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
            "private": {"seeds": {"WHEAT": 1, "MELON": 1, "STRAWBERRY": 1}, "shed": {}},
        }
        specs = agent._crop_specs(obs)
        route = agent._mixed_farm_route(obs, specs, obs["private"]["seeds"])
        self.assertEqual("STRAWBERRY", route["crop"])
        self.assertEqual([], route["market"])
        self.assertEqual("Apache-2.0", agent.MIXED_FARM_ROUTE_SOURCE["license"])

    def test_mixed_farm_route_flag_records_firing_without_online_dependency(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 1, "total_days": 30,
            "crops": {"WHEAT": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3, "fallback_price": 15}},
            "market": {"prices": {"WHEAT": 15}},
            "farms": [{"money": 200, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
            "private": {"seeds": {"WHEAT": 1}, "shed": {}},
        }
        agent.LONG_HORIZON_MIXED_FARM_ROUTE = True
        before = agent.MIXED_FARM_ROUTE_FIRES
        result = agent.agent(obs)
        self.assertEqual(before + 1, agent.MIXED_FARM_ROUTE_FIRES)
        self.assertEqual({"farmer", "hands", "market"}, set(result))
        self.assertLessEqual(len(result["market"]), 10)
        self.assertNotIn("UNKNOWN", [action[1] for action in result["market"] if len(action) > 1])

    def test_adaptive_route_expert_is_public_and_private_mutation_resistant(self):
        from scripts.measure_adaptive_route_repair import AdaptiveRouteOverlay, SOURCE
        agent = load_agent(ROOT / "main.py")
        overlay = AdaptiveRouteOverlay(agent)
        obs = {
            "player": 0, "day": 5,
            "farms": [
                {"money": 200, "farmer": [0, 0], "hands": [],
                 "tiles": [[{"kind": "WEED"}, None], [None, None]]},
                {"money": 999, "farmer": [0, 0], "hands": [],
                 "tiles": [[None, None], [None, None]]},
            ],
            "private": {"seeds": {"WHEAT": 1}, "shed": {"SECRET": 1}},
        }
        specs = agent._crop_specs(obs)
        expected = overlay.public_route_expert(obs, specs)
        obs["private"] = {"seeds": {"SECRET": 999}, "future_route": ["EAST"]}
        obs["farms"][1]["money"] = 1
        self.assertEqual("RECOVERY", expected)
        self.assertEqual(expected, overlay.public_route_expert(obs, specs))
        self.assertEqual("MIT", SOURCE["license"])

    def test_adaptive_suffix_repair_is_bounded_and_collision_safe(self):
        from scripts.measure_adaptive_route_repair import AdaptiveRouteOverlay
        agent = load_agent(ROOT / "main.py")
        overlay = AdaptiveRouteOverlay(agent)
        me = {"farmer": [0, 0], "hands": [[2, 0]],
              "tiles": [["LOCKED", "LOCKED", "LOCKED"],
                        [{"kind": "WEED"}, "LOCKED", {"kind": "WEED"}]]}
        before = overlay.counts()["adaptive_suffix_repair"]
        actions = overlay.bounded_suffix_repair(me, [["PASS"], ["PASS"]], 1,
                                                 agent.DEFAULT_CROPS, radius=3)
        self.assertEqual([["SOUTH"], ["SOUTH"]], actions)
        destinations = [agent._next_position(position, action)
                        for position, action in zip(([0, 0], [2, 0]), actions)]
        self.assertEqual(2, len(set(destinations)))
        self.assertEqual(before + 2,
                         overlay.counts()["adaptive_suffix_repair"])
    def test_late_capital_latch_is_public_one_shot_and_suppresses_investment(self):
        from scripts.measure_late_capital_latch import _load, _wrapper

        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / "latch.py"
            _wrapper(wrapper, ROOT / "main.py", True)
            candidate = _load(wrapper)
            farms = [
                {"money": 9000, "farmer": [0, 0], "hands": [], "hires_today": 0, "tiles": [[None]]},
                {"money": 1000, "farmer": [0, 0], "hands": [], "hires_today": 0, "tiles": [[None]]},
            ]
            obs = {
                "player": 0, "step": 577, "day": 24, "hour": 1,
                "turns_per_day": 24, "total_days": 30, "episode_steps": 720,
                "farms": farms,
                "private": {"shed": {}, "seeds": {"WHEAT": 0}, "inventories": [{}]},
                "market": {"inventory": {"WHEAT": 10000}, "prices": {"WHEAT": 25}},
            }
            first = candidate.agent(obs)
            self.assertFalse(any(order[0] in {"BUY_SEED", "HIRE"} for order in first["market"]))
            self.assertTrue(candidate.LATCH[0]["latched"])
            # Once decided, later rival cash changes cannot relatch or inspect private state.
            obs["step"], obs["farms"][1]["money"] = 578, 20000
            candidate.agent(obs)
            self.assertTrue(candidate.LATCH[0]["latched"])
            self.assertEqual({"latched", "eligible", "step", "remaining_turns", "cash_margin",
                              "rival_recoverable_cap", "reserve"}, set(candidate.LATCH[0]))

    def test_cash_reserve_and_market_order_cap_are_preserved(self):
        agent = load_agent(ROOT / "main.py")
        crops = {f"CROP{i}": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3,
                              "fallback_price": 20, "sell_above": 10} for i in range(12)}
        obs = {
            "player": 0, "day": 2, "crops": crops,
            "market": {"prices": {crop: 20 for crop in crops}},
            "farms": [{"money": 109, "farmer": [0, 0], "hands": [], "hires_today": 0, "tiles": [["LOCKED"]]}],
            "private": {"shed": {crop: 1 for crop in crops}, "seeds": {}, "inventories": [[]]},
        }
        result = agent.agent(obs)
        self.assertLessEqual(len(result["market"]), 10)
        self.assertFalse(any(action[0] in {"BUY_SEED", "HIRE"} for action in result["market"]))

    def test_price_aware_strategy_holds_inventory_below_target(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 3,
            "crops": {"CORN": {"seed_price": 18, "maturity_days": 3, "expected_yield": 4,
                                  "fallback_price": 14, "sell_above": 17}},
            "market": {"prices": {"CORN": 12}},
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [["LOCKED"]]}],
            "private": {"shed": {"CORN": 5}, "seeds": {}, "inventories": [[]]},
        }
        self.assertFalse(any(action[0] == "SELL" for action in agent.agent(obs)["market"]))

    def test_finite_horizon_prefers_crop_with_more_realizable_profit(self):
        agent = load_agent(ROOT / "main.py")
        obs = {
            "player": 0, "day": 8, "total_days": 12,
            "crops": {
                "FAST": {"seed_price": 10, "maturity_days": 1, "expected_yield": 2,
                         "fallback_price": 12, "price_forecast": [12] * 12},
                "SLOW": {"seed_price": 10, "maturity_days": 4, "expected_yield": 10,
                         "fallback_price": 20, "price_forecast": [20] * 12},
            },
            "market": {"prices": {"FAST": 12, "SLOW": 20}},
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}],
            "private": {"shed": {}, "seeds": {"FAST": 1, "SLOW": 1}, "inventories": [[]]},
        }
        crop, _ = agent._choose_crop(obs, obs["private"]["seeds"])
        self.assertEqual("FAST", crop)

    def test_finite_horizon_waits_for_forecast_peak_and_sells_on_final_day(self):
        agent = load_agent(ROOT / "main.py")
        base = {
            "player": 0, "total_days": 3,
            "crops": {"WHEAT": {"seed_price": 10, "maturity_days": 2, "expected_yield": 3,
                                    "fallback_price": 10, "sell_above": 10,
                                    "price_forecast": [10, 20, 15]}},
            "farms": [{"money": 100, "farmer": [0, 0], "hands": [], "tiles": [["LOCKED"]]}],
            "private": {"shed": {"WHEAT": 2}, "seeds": {}, "inventories": [[]]},
        }
        day_zero = dict(base, day=0, market={"prices": {"WHEAT": 10}})
        self.assertFalse(any(order[0] == "SELL" for order in agent.agent(day_zero)["market"]))
        final_day = dict(base, day=2, market={"prices": {"WHEAT": 15}})
        self.assertTrue(any(order[0] == "SELL" for order in agent.agent(final_day)["market"]))

    def test_report_maps_champion_candidate_and_submission_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            argv = ["evaluate.py", "--champion", str(ROOT / "tests/fixtures/champion_sot_2263.py"),
                    "--candidate", str(ROOT / "main.py"), "--fixture",
                    str(ROOT / "tests/fixtures/evaluation.json"), "--output", str(output)]
            with mock.patch("sys.argv", argv):
                self.assertEqual(0, evaluator.main())
            report = json.loads(output.read_text())
        self.assertEqual(str(ROOT / "main.py"), report["provenance"]["candidate"])
        self.assertEqual("submission.tar.gz", report["provenance"]["submission_artifact"])
        self.assertEqual(4, report["oracle"]["version"])
        self.assertEqual(10, report["submission_contract"]["max_market_orders"])
        self.assertIn("screen", report["competitive_oracle"])
        self.assertTrue(report["opponent_policy"]["screen"]["passed"])
        self.assertTrue(report["opponent_policy"]["confirm"]["passed"])
        if report["competitive_oracle"]["screen"]["passed"]:
            self.assertTrue(report["competitive_oracle"]["confirm"]["passed"])
            self.assertIsInstance(report["competitive_oracle"]["confirm"]["scenarios"], list)
        else:
            self.assertTrue(report["competitive_oracle"]["confirm"]["skipped"])


if __name__ == "__main__":
    unittest.main()

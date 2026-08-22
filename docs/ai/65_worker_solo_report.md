# Solo Worker Report — SOT-2974

## Summary

Pinned and independently packaged Kaito v19 Replication-to-Control as an exact
Apache-2.0, standard-library whole-agent hedge. It is distinct from v39's
sparse delayed-history gate: v19 refreshes a four-expert whole route and adds
clone-aware late inventory/collision control. The candidate passed the
same-seed/both-seat screen and disjoint confirm. It remains default-OFF;
production `main.py` and `submission.tar.gz` are unchanged.

## Changed Files

- `candidates/kaito-v19-replication-control/` — exact licensed agent, provenance, notice, and documentation
- `scripts/measure_kaito_v19_replication_control.py` — gated lineage/time-separated evaluator
- `docs/measurements/SOT-2971/SOT-2974-kaito-v19-replication-control.json` — closed-loop episode evidence
- `docs/ai/experiment_ledger.jsonl` — promoted cycle-6 axis with direct evidence
- `tests/test_kaito_v19_replication_control.py` — provenance, contract, novelty, holdout, and hedge checks
- `docs/ai/linear/SOT-2974.md` — local issue record

## Verification

- Python compileall: PASS
- Submission build, archive shape, and contract validator: PASS
- Unit tests: PASS (208 tests, 2 expected upstream-checkout-dependent skips)
- Screen: 4/4 DONE at 720 steps; rank 2.0→1.0; mean-margin delta +144297.5; p20/worst +165379
- Confirm: 4/4 DONE at 720 steps; rank 2.0→1.0; mean-margin delta +134641.25; p20/worst +141737
- npm lint/typecheck/test/e2e: N/A (Python repository; no `package.json` or e2e suite)
- Diff review: scoped; champion/archive unchanged; no private trace or Kaggle submission

## Acceptance Criteria

- [x] v39との差分と新規 whole-agent 根拠を記録
- [x] source version/hash/license/可搬性を固定
- [x] lineage/time-separated screen→confirm を実施
- [x] 実験台帳へ証拠付き promoted 判定を追記

## Risks

Local engine panels are transfer proxies rather than leaderboard proof. The
candidate is retained only as a default-off hedge and was not submitted.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

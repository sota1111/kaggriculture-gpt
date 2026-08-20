# Solo Worker Report

## Summary

Evaluated a public-observation productive-action capacity controller against the champion. The independent candidate fired 5,760 times, but reduced WATER/HARVEST/FERTILIZE actions and regressed screen and confirm tails, so the strict gate rejected it. The runtime flag remains disabled; evidence, tests, source boundary, and the rejected-axis ledger entry are retained.

## Changed Files

- `main.py` — dormant independent capacity flag, public throughput/backlog estimator, and source boundary; default remains false.
- `scripts/measure_productive_action_capacity.py` — same-seed/both-seat screen and independent confirm ablation.
- `tests/test_evaluate.py` — public/private boundary, disabled-default, schema, and rejection-gate coverage.
- `docs/measurements/SOT-2811/SOT-2814-productive-action-capacity.json` — complete A/B evidence.
- `docs/ai/experiment_ledger.jsonl` — rejected-axis result.
- `docs/ai/linear/SOT-2814.md` — local lifecycle record.

## Verification

- Python compile: PASS
- Unit tests: 70/70 PASS
- Submission contract/archive: PASS
- Component firing: 5,760
- Runtime ratio: 1.029; invalid actions 0; contract violations 0
- Screen lower-tail/worst margin: 213 → 80 (regression)
- Confirm lower-tail/worst margin: -1338 → -1471 (regression)
- WATER/HARVEST/FERTILIZE: 8,272 → 8,128 (rejected)
- npm lint/typecheck/test/e2e: N/A (no package manifest; offline Python agent)
- Kaggle submission: NOT PERFORMED

## Acceptance Criteria

- [x] Capacity uses public clock, worker positions, and crop-service backlog only; private-only mutation test passes.
- [x] Independent flag ablation records firing in same-seed/both-seat screen and independent confirm.
- [x] Rank, tail, runtime, invalid actions, and submission contract were checked; regressions were not hidden.
- [x] Non-promoted runtime remains disabled and the generated archive was restored to the champion artifact.
- [x] Evidence was appended to the experiment ledger; no Kaggle submission was performed.

## Risks

- This capacity formulation is closed unless new evidence changes its throughput estimator or promotion case.

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

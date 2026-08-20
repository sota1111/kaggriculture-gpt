# Solo Worker Report — SOT-2852

## Summary

Implemented a default-OFF, public-state capacity-aware closed-loop dispatcher. It fixes standing-on-work first, allocates visible task tiers against remaining workforce/action capacity, and adds explicit travel and productive-density opportunity costs. The same-seed/both-seat screen fired 2,880 times and reduced travel, but productive density regressed, so the strict gate rejected promotion, skipped confirm, and preserved the champion path. PR #67 was merged as `c2b1e2c`; no Kaggle submission occurred.

## Changed Files

- `main.py` — dispatcher flag, per-turn tier/travel budgets, scoring, telemetry.
- `scripts/measure_capacity_dispatcher.py` — screen-first paired A/B and promotion gate.
- `tests/test_evaluate.py` — default-OFF, public-state, standing-work, firing coverage.
- `docs/measurements/SOT-2850/SOT-2852-capacity-dispatcher.json` — complete A/B evidence.
- `docs/ai/experiment_ledger.jsonl` — rejected axis record.
- `submission.tar.gz` — verified default-OFF archive.

## Verification

- Python compileall: PASS.
- Unit tests: 105/105 PASS.
- GitHub CI submission / GitGuardian: PASS.
- Submission archive and source exec compatibility: PASS.
- Diff review and mergeability: PASS; no conflict.
- npm lint/typecheck/e2e: N/A (Python-only repository; no package.json/e2e configuration).
- Linear status: In Review; PR and Completion Report posted.

## Acceptance Criteria

- [x] Dispatcher budgets are recomputed each turn from public clock, visible task tiers, and worker positions.
- [x] Tier capacity/travel intervention logged: 2,880 firings; 1,508 harvest, 1,576 water, 112 plant assignments.
- [x] Same-seed/both-seat direct screen saved; confirm skipped because screen did not pass.
- [x] Reward tails did not regress (+110 mean/lower-tail/worst), but productive density regressed 0.445652 to 0.441496, so no promotion.
- [x] Candidate remains default-OFF and champion behavior is preserved.
- [x] Submission contract and exec compatibility pass.
- [x] Kaggle submission was not performed.

## Risks

The candidate reduced travel from 3,488 to 3,144 but also reduced productive actions from 5,576 to 5,524. It is retained only as an auditable, disabled ablation; there is no production-policy change.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

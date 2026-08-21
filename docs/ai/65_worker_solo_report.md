# Solo Worker Report — SOT-2907

## Summary

Implemented the SOT-2906-fired step-0 `market` family as an independently attributable candidate.
`PUBLIC_STEP0_WHEAT_MARKET_LEAD` defaults to `False`; when explicitly enabled, its narrow trigger
prepends `BUY_PRODUCT WHEAT 5` without changing worker actions or the existing market plan.

## Changed Files

- `main.py` — default-off candidate, pinned provenance/boundary, and per-seat firing telemetry.
- `tests/test_evaluate.py` — both-seat firing and exact-control invariance tests.
- `scripts/measure_public_step0_wheat_market_lead.py` — targeted ablation and full-game exec smoke.
- `docs/measurements/SOT-2905/SOT-2907-public-step0-wheat-market-lead.{json,md}` — evidence.
- `docs/ai/experiment_ledger.jsonl` — inconclusive candidate entry pending sealed confirm.
- `submission.tar.gz` — rebuilt archive matching the default-off champion.

## Verification

- Python compile: PASS.
- Unit tests: PASS, 134/134.
- Submission archive/action contract: PASS.
- Targeted ablation: both seats fire once; flag-off/non-trigger/non-market exact invariance PASS.
- Full-game exec smoke: candidate in both seats, 2/2 episodes `DONE/DONE`, step-0 order observed.
- Deterministic rerun: byte-identical SHA-256 `5285e19e671412f13253565b5a288d7fa57cbd3e8e2aa9156c7d0c079d680d03`.
- `git diff --check`: PASS.
- npm lint/typecheck/test/e2e: N/A; Python-only repository with no `package.json`.
- Kaggle submission: NOT PERFORMED; SOT-2908 confirm remains `RESERVED_UNOPENED`.
- GitHub: PR #95 created; merge/check result is recorded in Linear completion reporting.

## Acceptance Criteria

- [x] SOT-2906 prerequisite confirmed: market first at step 0 in 4/4 screen episodes.
- [x] Portable boundary and source URL/version/hash/license status recorded.
- [x] Candidate is independently attributable and default-off.
- [x] Non-target behavior and exec compatibility are preserved.
- [x] No Kaggle submission occurred.

## Risks

This run establishes an attributable candidate, not causal uplift. The result remains inconclusive until
SOT-2908 evaluates the still-unopened sealed both-seat panel. The source notebook has no declared license;
therefore no source code or route was copied, only the observed five-WHEAT action was independently expressed.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

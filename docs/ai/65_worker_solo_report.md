# Solo Worker Report — SOT-2972

## Summary

Pinned and independently packaged the Apache-2.0 Moon Counts Melons V102
whole agent. The candidate passed the stdlib `main.py:agent` contract, the
same-seed/both-seat screen, and the disjoint sealed confirm. It remains
default-OFF; production `main.py` and `submission.tar.gz` are unchanged.

## Changed Files

- `candidates/moon-counts-melons/` — licensed agent, provenance, notice, and documentation
- `scripts/measure_moon_counts_melons.py` — reproducible gated screen/confirm runner
- `docs/measurements/SOT-2971/SOT-2972-moon-counts-melons.json` — real episode evidence
- `docs/ai/experiment_ledger.jsonl` — promoted cycle-6 axis with evidence
- `tests/test_moon_counts_melons.py` — provenance, contract, holdout, and hedge checks
- `docs/ai/linear/SOT-2972.md` — local issue record

## Verification

- Python compileall: PASS
- Submission contract validator: PASS
- Unit tests: PASS (199 tests, 2 upstream-checkout-dependent skips), plus SOT-2972 tests
- Screen: 4/4 DONE at 720 steps; rank 2.0→1.0; mean margin delta +155871.75; p20/worst +190814
- Confirm: 4/4 DONE at 720 steps; rank 2.0→1.0; mean margin delta +109845.75; p20/worst +142325
- npm lint/typecheck/test/e2e: N/A (Python repository; no `package.json` or e2e suite)
- Diff review: scoped; champion/archive SHA-256 unchanged

## Acceptance Criteria

- [x] Source version, hashes, Apache-2.0 license, and portability recorded
- [x] Independent package is stdlib/offline and contract/exec compatible
- [x] Screen and sealed confirm completed with action firing hashes/counts
- [x] Experiment ledger records promoted with direct evidence

## Risks

- Local engine panels remain proxy evidence; no Kaggle submission was made by this child issue.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

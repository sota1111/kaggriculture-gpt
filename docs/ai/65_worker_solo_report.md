# Solo Worker Report

## Summary

Evaluated a source-attributed cash-runway-aware incremental acreage component. The independent candidate fired for land, hire, plant, and water in both seats, but strict screen/confirm and cash gates rejected it. Production behavior was reverted by leaving the flag disabled; only evidence, tests, provenance, and the ledger entry remain.

## Changed Files

- `main.py` — dormant, independently toggled candidate and source boundary; default flag is false.
- `scripts/measure_runway_acreage.py` — same-seed/both-seat screen and independent confirm measurement.
- `tests/test_evaluate.py` — reserve, firing, source-boundary, disabled-default, and rejection-gate coverage.
- `docs/measurements/SOT-2811/SOT-2813-runway-acreage.json` — complete A/B evidence.
- `docs/ai/experiment_ledger.jsonl` — rejected-axis result.
- `docs/ai/linear/SOT-2813.md` — local lifecycle record.

## Verification

- Python compile: PASS
- Unit tests: 68/68 PASS
- Submission contract: PASS
- Runtime ratio: 0.994; invalid actions 0; contract violations 0
- npm lint/typecheck/test/e2e: N/A (no package manifest; offline Python agent)
- Kaggle submission: NOT PERFORMED

## Acceptance Criteria

- [x] Source, MIT license, SHA-256, and distilled/excluded boundaries recorded.
- [x] Independent flag and both-seat direct A/B with firing evidence recorded.
- [x] Confirm rank/runtime/contract measured; tail regression detected rather than hidden.
- [x] Non-promoted production runtime remains disabled.
- [x] Ledger evidence appended; no Kaggle submission performed.

## Risks

- The tested axis is closed without new evidence because both tail and cash metrics regressed.

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

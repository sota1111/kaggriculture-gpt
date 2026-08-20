# Solo Worker Report — SOT-2850

## Summary

Aggregated completed children SOT-2851/SOT-2852/SOT-2853. The measurement oracle was promoted, but the capacity-aware runtime dispatcher was rejected by the sealed direct A/B because productive density regressed and repair work increased. Confirm remained sealed, the dispatcher stays default-OFF, no artifact was promoted, and the strict improvement gate required no Kaggle submission.

## Changed Files

- `docs/ai/experiment_ledger.jsonl` — parent aggregation and strict no-submit decision.
- `docs/ai/linear/SOT-2850.md` — child results, submission decision, and handoff.
- `docs/ai/65_worker_solo_report.md` — final solo lifecycle report.

## Verification

- Python compileall: PASS.
- Unit tests: 107/107 PASS.
- Submission contract and last-callable exec compatibility: PASS.
- Existing submission archive integrity and `main.py` equivalence: PASS.
- Deterministic sealed evidence: PASS.
- npm lint/typecheck/e2e: N/A (Python-only repository; no package.json/e2e configuration).

## Acceptance Criteria

- [x] Improvement direction and rationale recorded.
- [x] All children reached Done and their results were aggregated.
- [x] Candidate/evidence correspondence and effective default-OFF config recorded.
- [x] No-submit decision explicitly recorded because no champion was promoted.
- [x] Rejection is backed by same-seed/both-seat direct A/B and 2,880 firings.
- [x] Handoff prepared for the parent completion comment.

## Risks

The disabled candidate remains an auditable ablation. A future cycle should use a new upstream useful-work-per-repair assignment objective and must not retry this rejected axis without new evidence.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

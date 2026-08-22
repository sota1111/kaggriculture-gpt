# Solo Worker Report — SOT-2986

## Summary

Aggregated four completed child directions. Apache Agent Builder clean-room was the strongest portable local candidate, was packaged and submitted through the governed control-plane path, and scored public 600.0. It is rejected for champion replacement; the incumbent remains preserved.

## Changed Files

- `submission.tar.gz` — exact Apache clean-room live-observation artifact.
- `docs/ai/experiment_ledger.jsonl` — selection, effective fingerprint, submission, and rejection evidence.
- `docs/ai/linear/SOT-2986.md` — parent lifecycle record.

## Commands Run

- Submission contract and archive integrity: PASS.
- `python3 -m compileall -q .`: PASS.
- `python3 -m unittest discover -s tests -v`: 241 passed, 2 optional skips.
- npm lint/typecheck/test/e2e: N/A (Python-only repo, no package.json/UI).
- Governed Kaggle submit: ref 55687715 COMPLETE, public 600.0.

## Acceptance Criteria

- [x] Improvement directions and rationale recorded.
- [x] SOT-2987/SOT-2989/SOT-2990/SOT-2991 all terminal Done.
- [x] Candidate, effective-config fingerprint, validation, and live result mapped in the ledger.
- [x] Parent resume confirmed all children and submitted a new artifact.
- [x] Rejection has exact-artifact live intervention evidence; unsupported oracle conclusions remain separated.
- [x] Handoff comment prepared for Linear.

## Risks

- Fixed-opponent local panels again failed to predict live ordering; do not use them for promotion.
- Apache clean-room, Conditional Memory, V111, and R5A must not be retried without new opponent-distribution evidence.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

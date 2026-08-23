# Solo Worker Report — SOT-3013

## Summary

Aggregated all three completed children, verified and submitted the immutable C95 whole-agent through the governed helper, and observed Kaggle ref `55701484` at public `600.0`. This is below the immediately prior incumbent ref `55690743` at `792.7`, so C95 is rejected for live promotion and the incumbent remains the hedge.

## Verification

- Archive SHA-256: `8af1fcb0574a043e57577ccb605a7e0c30a5f9d92717ea601542e3b163e5c7d9`.
- Sole `main.py` member SHA-256: `ed8c8420514acb5a96c0d44cfd42a8786e49c7cdc01a0de61d2e6b8997dda87a`.
- Effective-config fingerprint: `cd276b276df40fdd4c0c8b855991b1f59e0c3634db997af24e5eb8b434c1d04a`.
- Python compile: PASS.
- Unit tests: PASS (275 tests, 2 optional skips).
- Reserve/spacing/cap gates: PASS; no bypass.
- Kaggle ref `55701484`: COMPLETE, public `600.0`.
- Current-field final holdout: unopened.

## Acceptance Criteria

- [x] Improvement strategy and rationale recorded.
- [x] All child issues are Done.
- [x] Candidate, hashes, effective config, submission ref, and result are mapped.
- [x] Parent resume confirmed children and submitted the corrected artifact.
- [x] Rejection is backed by direct live comparison against the prior incumbent submission.
- [x] Handoff and Completion Report posted to Linear.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

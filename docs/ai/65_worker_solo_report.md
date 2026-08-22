# Solo Worker Report — SOT-3004

## Summary

Reproduced the Apache-2.0 C95 notebook's embedded agent byte-for-byte, packaged it as a default-off offline candidate, and completed a 720-turn both-seat screen plus opponent/lineage/episode/seed/seat/time-disjoint confirm. The candidate is promoted only as a structurally independent working-baseline hedge; the incumbent and submission archive remain unchanged and no Kaggle submission occurred.

## Changed Files

- `candidates/c95-high-score/` — exact agent, provenance, license, and package boundary.
- `scripts/extract_c95_exact.py` — fail-closed notebook/artifact extractor.
- `scripts/measure_c95_high_score.py` — screen/confirm and runtime evidence runner.
- `tests/test_c95_high_score.py` — identity, portability, and evidence contracts.
- `docs/measurements/SOT-3004/c95-screen-confirm.json` — sealed evidence and effective-config fingerprint.
- `docs/ai/experiment_ledger.jsonl` / `docs/ai/linear/SOT-3004.md` — decision ledger and issue record.

## Verification

- Notebook SHA-256: `cdca09ed40f2c3a8b142791dd2f1b5f3dffc2de4332a153e53da6c63d58e7b5a`.
- Exact agent: 133270 bytes, SHA-256 `ed8c8420514acb5a96c0d44cfd42a8786e49c7cdc01a0de61d2e6b8997dda87a`.
- Compile and file-runner submission contracts: PASS.
- Full unit suite: 249 PASS, 2 optional skips.
- Screen: 4/4 wins-or-ties; mean-margin delta +139739.5; p20/worst delta +125000.
- Confirm: mean-margin delta +163872.25; p20/worst delta +156084.
- All eight candidate games ended DONE/DONE at 720 turns; zero invalid actions; 64894 non-PASS actions.
- Effective-config fingerprint: `cd276b276df40fdd4c0c8b855991b1f59e0c3634db997af24e5eb8b434c1d04a`.
- Kaggle submission: NOT_PERFORMED.

## Acceptance Criteria

- [x] License/source/notebook/artifact identity fixed.
- [x] Candidate is offline, stdlib-only, file-runner callable, and fail-closed on extraction drift.
- [x] Screen/confirm, firing, runtime, and invalid-action evidence saved.
- [x] Evidence-backed promoted-hedge conclusion appended to the ledger.
- [x] No Kaggle submission; incumbent hedge preserved.

## Risks

This promotion is a local working-baseline/portfolio decision, not a champion replacement or leaderboard claim. The issue explicitly prohibits submission, so live transfer remains unobserved.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

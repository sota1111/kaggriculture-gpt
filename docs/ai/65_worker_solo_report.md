# Solo Worker Report — SOT-2944

## Summary

Implemented a deterministic, independently packaged V16-RC5-style 8C/4S premium-market candidate. The referenced Kaggle notebook and extracted agent hashes are pinned, but because no license was declared, the committed policy is a clean-room implementation from public prose only. The repository champion and submission archive remain unchanged.

The candidate is default-OFF. Its enabled artifact assigns existing livestock purchase slots toward the published herd milestones and reorders only existing premium SELL slots from current public price, inventory, town demand, and own-stock feasibility. Screen and reserved confirm identities are mechanically disjoint across lineage, episode, seed, seat, and time.

## Changed Files

- `candidates/v16-rc5-portable/` — clean-room policy, source/license boundary, and packaging notes.
- `scripts/package_v16_rc5_portable.py` — deterministic default-OFF/enabled artifact builder.
- `scripts/measure_v16_rc5_portable.py` — same-seed/both-seat screen and targeted firing evidence.
- `tests/fixtures/v16_rc5_portable.json` — pre-registered screen/confirm identities.
- `tests/test_v16_rc5_portable.py` — split, default-OFF, firing, and committed-result tests.
- `docs/measurements/SOT-2942/SOT-2944-v16-rc5-portable.json` — measurement evidence.
- `docs/ai/experiment_ledger.jsonl` — inconclusive axis entry.
- `README.md` / `docs/ai/linear/SOT-2944.md` — usage and lifecycle record.

## Verification

- Source notebook SHA-256 `92faf3269de09bdf8bcbb3d306f12cf8a8d83385e9cec94b78f6134a04d4143f`; extracted published code SHA-256 `8315d985716c625c31be795e51912276bdbd6cdcb37b2a02a8a1db49e5cd9154`.
- 159 tests passed; 2 unrelated optional upstream-checkout tests skipped.
- Python compilation passed.
- Submission contract and exec compatibility passed for the enabled generated artifact.
- `git diff --check` passed.
- Screen: four 720-step episodes, same seeds in both seats, all `DONE/DONE`.
- Candidate tied baseline: mean rank 2.0; mean/p20/worst margin -146754.25/-171384/-171384.
- Natural screen decision-family delta was zero; this is recorded rather than hidden.
- Targeted public-state interventions fired the independent gate in both seats while preserving order count and the SELL multiset.
- Confirm outcomes remain unopened for SOT-2947; public-best was not used and no Kaggle submission occurred.

## Risks

The natural screen did not exercise the candidate and produced no uplift, so the axis is inconclusive and must remain default-OFF. Only the common portfolio gate may decide whether later confirm evidence warrants further consideration.

## Linear Report: PENDING

Pending final lifecycle sync; this line is updated only after the completion comment succeeds.

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

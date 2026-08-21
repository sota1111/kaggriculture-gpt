# Solo Worker Report — SOT-2945

## Summary

Implemented a deterministic, independently packaged Strict-Future meta-reset candidate. The referenced Kaggle notebook and embedded agent hashes are pinned, but because no license was declared, the committed policy is a clean-room implementation from public prose only. The repository champion and submission archive remain unchanged.

The candidate is default-OFF. Its enabled artifact uses a bounded sheep-first opening redirection and reorders only existing SELL slots from current public price, inventory, and town demand. The chronological screen and reserved confirm identities are mechanically disjoint across lineage, episode, seed, seat, and time.

## Changed Files

- `candidates/strict-future-meta-reset/` — clean-room policy, source/license boundary, and packaging notes.
- `scripts/package_strict_future_meta_reset.py` — deterministic default-OFF/enabled artifact builder.
- `scripts/measure_strict_future_meta_reset.py` — same-seed/both-seat chronological screen and targeted firing evidence.
- `tests/fixtures/strict_future_meta_reset.json` — pre-registered screen/confirm identities.
- `tests/test_strict_future_meta_reset.py` — split, default-OFF, firing, and committed-result tests.
- `docs/measurements/SOT-2942/SOT-2945-strict-future-meta-reset.json` — measurement evidence.
- `docs/ai/experiment_ledger.jsonl` — inconclusive axis entry.

## Verification

- 156 tests passed; 2 unrelated optional upstream-checkout tests skipped.
- Python compilation passed.
- Submission contract and exec compatibility passed for the enabled generated artifact.
- `git diff --check` passed.
- Screen: four 720-step episodes, same seeds in both seats, all `DONE/DONE`.
- Candidate tied baseline: mean rank 2.0; mean/p20/worst margin -134584.5/-136016/-136016.
- Natural screen decision-family delta was zero; this is recorded rather than hidden.
- Targeted public-state interventions fired the independent gate in both seats while preserving order count and the SELL multiset.
- Confirm outcomes remain unopened for SOT-2947; public-best was not used and no Kaggle submission occurred.

## Risks

The natural screen did not exercise the reset and produced no uplift, so the axis is inconclusive and must remain default-OFF. Only the common portfolio gate may decide whether later confirm evidence warrants further consideration.

## Linear Report: PENDING

Pending final lifecycle sync; this line is updated only after the completion comment succeeds.

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

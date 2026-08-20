# Solo Worker Report — SOT-2832

## Summary

Implemented a deterministic decision-family attribution harness for the pinned 4,320-row winner-only teacher corpus. The screen selected `economic`; the entity/episode/seed/seat/time-separated confirm panel independently agreed. Land and labor remain CLOSED. Runtime policy and Kaggle submission artifact are unchanged.

## Changed Files

- `scripts/measure_decision_family_divergence.py` — leak-free first-action family measurement and screen→confirm gate.
- `docs/measurements/SOT-2832/SOT-2832-decision-family-divergence.json` — reproducible aggregate evidence and provenance hashes.
- `tests/test_evaluate.py` — family mapping, artifact boundary, and first-action tests.
- `README.md`, `docs/ai/experiment_ledger.jsonl`, `docs/ai/linear/SOT-2832.md` — reproduction and outcome records.

## Verification

- Deterministic artifact rerun: PASS, byte-identical SHA-256.
- Python compile: PASS.
- Unit tests: 87/87 PASS.
- Submission contract/build: PASS; generated archive was restored and its committed SHA-256 is unchanged.
- `main.py` and `submission.tar.gz`: unchanged from branch base.
- npm lint/typecheck/test and e2e: N/A (Python-only repository; no package.json or browser suite).
- Kaggle submission: NOT PERFORMED.

## Acceptance Criteria

- [x] Family frequency, reward-attribution proxy, and divergence recorded reproducibly.
- [x] Screen/confirm isolated by entity, episode, seed, seat, and time.
- [x] Land/labor CLOSED families excluded; economic selected with screen/confirm evidence.
- [x] Runtime candidate and Kaggle submission unchanged.
- [x] Experiment ledger updated.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

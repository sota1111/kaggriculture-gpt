# Solo Worker Report — SOT-2845

## Summary

Built and executed a hash-pinned, opponent-diverse, both-seat sealed closed-loop gate for the sequence planner. The strict rank-first screen rejected the candidate and correctly preserved confirm identities. The planner default was reverted to the champion (`false`), evidence was recorded, and no Kaggle submission was made.

## Changed Files

- `scripts/measure_sequence_planner_sealed_panel.py` — live paired A/B harness and screen→confirm gate.
- `tests/fixtures/sequence_planner_sealed_panel.json` — immutable artifacts and isolated identities.
- `docs/measurements/SOT-2842/SOT-2845-sequence-planner-sealed-panel.{json,md}` — all match rows, hashes, metrics, and decision.
- `main.py` / `submission.tar.gz` — rejected planner default reverted and champion archive rebuilt.
- `tests/test_evaluate.py` — strict rank/firing gate regression coverage.
- `docs/ai/experiment_ledger.jsonl` — rejected axis appended.
- `docs/ai/linear/SOT-2845.md` — lifecycle record.

## Verification

- Python compile: PASS.
- Unit tests: PASS (102/102).
- Sealed screen: completed (4 matches, two archetypes, both seats).
- Sealed confirm: correctly skipped because screen failed.
- Submission contract / exec compatibility: PASS.
- Deterministic archive: PASS (`cc15f7efe168a874132c91d74e0dd9c082b73517118ef8a0133c6e922d348819` twice).
- npm lint/typecheck/test and e2e: N/A (Python-only repository; no package.json or browser suite).
- Kaggle submission: NOT_PERFORMED.

## Acceptance Criteria

- [x] Opponent-diverse both-seat screen completed.
- [x] Confirm remained sealed after the screen failed.
- [x] Rank/tail/constraint/firing and productive/travel evidence saved with rows and hashes.
- [x] Rejection supported by direct A/B and live firing evidence and appended to ledger.
- [x] Submission contract and exec compatibility passed.
- [x] No Kaggle submission was executed.

## Linear Report: PENDING

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

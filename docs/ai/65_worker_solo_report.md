# Solo Worker Report — SOT-2758

## Summary

- Added mechanically validated opponent/seed/episode isolation across strictly ordered screen and confirm windows.
- Added deterministic champion/candidate paired A/B evaluation on identical seeds in both seat assignments.
- Added mean, lower-tail, worst, and relative-rank evidence plus terminal-bank-reward and leak checks.
- Recorded a promoted measurement and experiment-ledger entry. No Kaggle submission was made.

## Changed Files

- `scripts/evaluate.py` — holdout validation and paired two-seat A/B evaluator.
- `tests/fixtures/evaluation.json` — disjoint screen/confirm entity manifest.
- `tests/test_evaluate.py` — isolation, leak rejection, paired-seat, determinism, and summary coverage.
- `docs/measurements/SOT-2756/SOT-2758-leak-free-cv.json` — reproducible evidence.
- `docs/ai/experiment_ledger.jsonl` — promoted-axis record.

## Verification

- `python3 -m compileall -q main.py scripts tests`: PASS.
- `python3 -m unittest tests.test_evaluate`: PASS (40 tests).
- Full evaluation: PROMOTE; screen and confirm leak-free CV gates PASS.
- Screen reward delta mean/lower-tail/worst: +1808.5/+1758/+1758; candidate rank 1.0.
- Confirm reward delta mean/lower-tail/worst: +1866/+1820/+1820; candidate rank 1.0.
- `python3 scripts/validate_submission.py main.py`: PASS.
- npm lint/typecheck/test/e2e: N/A (no `package.json` or e2e harness).
- Kaggle submission: not executed.

## Acceptance Criteria

- [x] entity × temporal holdout is mechanically isolated.
- [x] same-seed champion/candidate direct A/B is reproducible across both seats.
- [x] leak/contract checks and screen→confirm pass.
- [x] evidence is recorded in the measurement and experiment ledger.

## Risks

- The local simulator remains a contract-shaped proxy rather than a Kaggle submission result; no submission was permitted or performed.

## Linear Report: POSTED
## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

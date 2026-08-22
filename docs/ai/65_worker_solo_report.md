# Solo Worker Report — SOT-3009

## Summary

Hamburger V27 was reconstructed as an independent, default-off clean-room whole-agent. The public snapshot did not declare a redistribution license, so no upstream source/blob/replay bytes were copied. The candidate passed offline/file-runner and runtime checks but failed the C95 confirmation panel, so it was rejected and not promoted into the working submission.

## Changed Files

- `candidates/hamburger-v27/` — provenance-pinned clean-room agent and portability documentation.
- `scripts/measure_hamburger_v27.py` — both-seat screen/confirm measurement and fingerprinting.
- `tests/fixtures/hamburger_v27.json` / `tests/test_hamburger_v27.py` — isolated identities and behavior/contract tests.
- `docs/measurements/SOT-3009/hamburger-v27-screen-confirm.json` — sealed result.
- `docs/ai/experiment_ledger.jsonl` — rejected axis entry.

## Verification

- Python compileall: PASS.
- Full unittest discovery: 261 tests passed, 2 optional skipped.
- File-runner smoke: 720 steps, both agents DONE.
- Screen vs incumbent: 2/0/0 W/D/L, mean margin +1,695.
- Confirm vs C95: 0/0/2 W/D/L, mean margin -164,034, worst -167,460.
- Runtime contract: PASS; effective-config fingerprint recorded.
- `git diff --check`: PASS.
- npm lint/typecheck/test/e2e: N/A (`package.json` absent).
- `main.py`, C95 agent, and `submission.tar.gz`: byte-identical to `origin/main`.
- Kaggle submission: NOT_PERFORMED.

## Acceptance Criteria

- [x] Source snapshot identity/hash/license and clean-room portability decision recorded.
- [x] Independent whole-agent executes offline and through the file runner.
- [x] Screen→confirm results and effective-config fingerprint recorded in measurement and ledger.
- [x] Incumbent/C95 remain unchanged; rejected candidate remains default-off.
- [x] No Kaggle submission performed.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

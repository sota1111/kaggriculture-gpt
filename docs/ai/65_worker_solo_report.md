# Worker Report — SOT-2822

## Summary

Added and executed a sealed screen→confirm promotion gate for the shop-prefix
route selector. The screen rejected the selector after a firing-logged paired
tie, so confirm was correctly skipped and the runtime flag remains off.

## Changed Files

- `scripts/measure_shop_prefix_closed_loop.py` — sealed same-seed/both-seat gate
- `tests/test_evaluate.py` — gate and raw-delta unit coverage
- `docs/measurements/SOT-2819/SOT-2822-shop-prefix-closed-loop.json` — raw evidence
- `docs/ai/experiment_ledger.jsonl` — rejected axis entry
- `docs/ai/linear/SOT-2822.md` — local issue record

## Verification

- `.venv/bin/python -m py_compile main.py scripts/*.py tests/test_evaluate.py` — PASS
- `.venv/bin/python -m unittest discover -s tests -v` — PASS (76 tests)
- sealed closed-loop measurement — PASS; candidate rejected, confirm skipped
- `.venv/bin/python scripts/validate_submission.py main.py` — PASS
- submission rebuild, gzip single-member/archive-content validation — PASS
- `git diff --check` and merge-conflict precheck — PASS
- npm lint/typecheck/test/e2e — N/A (Python-only repository; no package.json/browser)

## Acceptance Criteria

- [x] screen result and raw rows saved
- [x] rejection has same-seed A/B and selector firing records
- [x] promotion-only fingerprint handoff is not applicable
- [x] non-promoted runtime remains disabled
- [x] no Kaggle submission

## Risks

The selector fired but did not alter terminal behavior on the screen panel.

## Linear Report: PENDING

## Acceptance: PASS

## Next Action

READY_FOR_REVIEW

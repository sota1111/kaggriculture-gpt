# Solo Worker Report — SOT-2821

## Summary

Ported COK V7's first-three-public-shop selector as a portable, Apache-attributed ablation with five observable branches and normalized crop/livestock targets. The strict live screen tied in all four paired matches, so the selector remains disabled and the champion runtime is unchanged; evidence, tests, and the rejected ledger result are retained.

## Changed Files

- `main.py` — disabled public shop-prefix selector, branch counters, route targets, and bounded integration.
- `scripts/measure_shop_prefix_route.py` — same-seed/both-seat screen and gated confirm measurement.
- `tests/test_evaluate.py` — all-branch, leakage-resistance, and cash-feasibility tests.
- `docs/measurements/SOT-2819/SOT-2821-shop-prefix-route.json` — direct A/B and branch evidence.
- `docs/ai/experiment_ledger.jsonl` — rejected axis entry.
- `submission.tar.gz` — rebuilt validated offline artifact.

## Verification

- `python3 -m py_compile main.py scripts/*.py tests/test_evaluate.py` — PASS
- `python3 -m unittest discover -s tests -v` — PASS (74 tests)
- `python3 scripts/validate_submission.py main.py` — PASS
- `bash scripts/build_submission.sh` — PASS
- gzip/archive content checks — PASS
- `git diff --check` — PASS
- npm lint/typecheck/test/e2e — N/A (Python-only repository; no `package.json` or browser surface)

## Acceptance Criteria

- [x] Public observations only: first three unlocked shops; private/identity/episode/submission/seed mutation invariant.
- [x] All selector branches recorded in unit and measurement evidence.
- [x] Same-seed/both-seat A/B saved; non-improvement led to disabled runtime and rejected ledger result.
- [x] stdlib/offline submission compatibility preserved.
- [x] No Kaggle submission performed.

## Risks

- The selector was not promoted because the strict screen produced ties rather than improvement.
- Independent confirm was intentionally skipped by the predeclared screen gate.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

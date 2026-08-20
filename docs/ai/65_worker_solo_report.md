# Solo Worker Report — SOT-2779

## Summary

- Classified the issue as IMPLEMENT and judged decomposition unnecessary.
- Evaluated the Seyamalam V21 demand-timed premium-sale and matched-rival price-floor mechanism as an independent temporary candidate.
- Confirmed both-seat intervention firing and cap behavior, while keeping `PROJECTED_MARKET_EXECUTION` disabled.
- Rejected and reverted the production candidate because screen and confirm metrics tied the champion exactly; retained reproducible measurement/test/ledger evidence only.

## Changed Files

- `scripts/measure_demand_premium_sales.py` — temporary independent flag ablation, source attribution, matched-rival floor cap, firing evidence, and strict gate.
- `tests/test_evaluate.py` — strict-gate regression coverage.
- `docs/measurements/SOT-2777/SOT-2779-demand-premium-sales.json` — same-seed/both-seat screen and independent confirm evidence.
- `docs/ai/experiment_ledger.jsonl` — rejected axis, source, result, and evidence.
- `docs/ai/linear/SOT-2779.md` — lifecycle record.

## Verification

- Python compile — PASS.
- `python3 -m unittest discover -s tests` — PASS, 49 tests.
- Measurement rerun — PASS; decision and intervention results reproduced.
- `python3 scripts/validate_submission.py main.py` — PASS.
- Submission archive gzip/member validation — PASS (`main.py` only).
- npm lint/typecheck/test/e2e — N/A; Python-only repository without `package.json`.
- `git diff --check` and scoped diff review — PASS.
- Kaggle submission — NOT PERFORMED.
- Baseline and candidate screen rank/mean/lower-tail/worst: `1.0 / 1904 / 169 / 169`.
- Baseline and candidate confirm: `1.5 / -606.5 / -1382 / -1382`.
- Targeted both-seat interventions: MILK stock `20` capped to `18`; WOOL stock `20` capped to `10`.

## Acceptance Criteria

- [x] Candidate used current observation/own shed only and added no dependency.
- [x] Direct A/B and targeted both-seat firing evidence are recorded independently of the rejected projected-market axis.
- [x] Strict gate rejected the tie and production `main.py` was reverted.
- [x] Submission contract and exec compatibility pass.
- [x] Ledger records source URL, commit, license, rejected result, and evidence.
- [x] No Kaggle submission was performed.

## Risks

- The compact replay-identity corpus contains no premium production, so its direct A/B could only establish non-regression/tie; targeted observation cases establish mechanism firing but not competitive gain.
- The rejected axis must not be retried without new premium-producing replay evidence.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

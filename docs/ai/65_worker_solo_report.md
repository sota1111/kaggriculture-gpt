# Solo Worker Report — SOT-2780

## Summary

- Classified the child issue as IMPLEMENT and judged further decomposition unnecessary.
- Evaluated a Seyamalam V21-derived, independent public-state late-capital latch against the SOT-2778 replay-identity corpus.
- The latch made one persistent decision from observable horizon, cash margin, rival hands, and current prices; targeted screen/confirm cases suppressed additional investment in both seats.
- Rejected the candidate because rank, margin, lower-tail, and worst-case metrics tied the champion exactly. Production `main.py` remains unchanged; only measurement, test, attribution, and ledger evidence remain.

## Changed Files

- `scripts/measure_late_capital_latch.py` — isolated feature-flag ablation, one-shot latch, strict gate, attribution, and intervention evidence.
- `tests/test_evaluate.py` — public-state, persistence, and investment-suppression coverage.
- `docs/measurements/SOT-2777/SOT-2780-late-capital-latch.json` — same-seed/both-seat screen and independent-confirm results.
- `docs/ai/experiment_ledger.jsonl` — rejected axis with source URL, commit, digest, outcome, and evidence.
- `docs/ai/65_worker_solo_report.md` — lifecycle acceptance report.

## Verification

- Python compile — PASS.
- `python3 -m unittest discover -s tests -v` — PASS, 50 tests.
- Measurement rerun — PASS; decision, metrics, component counts, and interventions reproduced.
- `python3 scripts/validate_submission.py main.py` — PASS.
- `python3 scripts/validate_submission.py main.py --exec-check` — PASS.
- npm lint/typecheck/test/e2e — N/A; Python-only repository without `package.json`.
- `git diff --check` and scoped diff review — PASS; `main.py` has no diff.
- Kaggle submission — NOT PERFORMED.
- Screen baseline/candidate rank and mean/lower-tail/worst margin: `1.0 / 1904 / 169 / 169` (tie).
- Confirm baseline/candidate: `1.5 / -606.5 / -1382 / -1382` (tie).
- Runtime ratio: `0.776`; invalid actions and contract violations remained `0`.

## Acceptance Criteria

- [x] Public-state-only, dependency-free, one-shot persistent latch was evaluated in isolation.
- [x] Direct same-seed/both-seat A/B and targeted both-seat firing evidence are independent of terminal recovery.
- [x] Strict promotion gate rejected the tie and left production `main.py` unchanged.
- [x] Submission contract and exec compatibility pass.
- [x] Ledger records source URL, commit, MIT license, source digest, result, and evidence.
- [x] No Kaggle submission was performed.

## Risks

- The fallback replay corpus never presented a two-farm late-capital intervention to the candidate, so competitive A/B tied with zero natural firings; targeted both-seat cases prove mechanism behavior but not transferable gain.
- Do not retry this rejected axis without new late-game two-farm replay evidence.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

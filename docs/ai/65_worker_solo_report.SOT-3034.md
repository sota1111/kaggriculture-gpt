# Solo Worker Report — SOT-3034

## Summary

Implemented an engine-grounded transfer-attribution oracle that fixes the exact terminal-inventory /
market-impact identity, records public-only opponent-relative exposure, and emits phase-level co-firing
evidence. The official-engine fallback produced 2,436 market/terminal and 2,354 opponent-exposure
co-firings with zero identity residual across four complete same-seed/both-seat episodes.

The current-field join remains correctly inconclusive: its metadata records C95 margin drift from
`+1,333.3` in screen to `-700.0` in confirm, but contains no safe action/private trajectories for causal
component attribution. No candidate or policy was changed, and no Kaggle submission was performed.

## Changed Files

- `scripts/evaluation/trajectory_attribution.py` — exact terminal/market identity and public opponent
  exposure interaction metrics.
- `scripts/measure_engine_transfer_attribution.py` — official-engine both-seat measurement and safe
  current-field association.
- `tests/evaluation/test_trajectory_attribution.py` — synthetic identity and interaction firing tests.
- `tests/test_engine_transfer_attribution.py` — metadata-only current-field inconclusive contract test.
- `docs/measurements/SOT-3034/engine-transfer-attribution.json` — machine-readable evidence.
- `docs/measurements/SOT-3034/engine-transfer-attribution.md` — provenance, result, and SOT-3017 delta.
- `docs/ai/experiment_ledger.jsonl` — cycle-6 inconclusive axis entry.
- `docs/ai/linear/SOT-3034.md` — local lifecycle record.

## Commands Run

- `python3 -m unittest tests.evaluation.test_trajectory_attribution tests.test_engine_transfer_attribution -v` — 6 passed.
- `python3 scripts/measure_engine_transfer_attribution.py` — contract PASS; result inconclusive; firing recorded.
- `python3 -m unittest discover -s tests -v` — 285 passed, 2 skipped.
- `python3 -m compileall -q scripts tests` — pass.
- `git diff --check` — pass.
- npm lint/typecheck/test/e2e — N/A; no `package.json` or browser surface.

## Acceptance Criteria

- [x] Engine identity is fixed by tests: terminal market value equals engine-base inventory plus market impact with zero residual.
- [x] Market/terminal/opponent interaction firing evidence is recorded in official-engine trajectories and current-field association is separately bounded.
- [x] Difference from SOT-3017 is explicit: exact cross-term residual, public opponent exposure, phase firing, and newer current-field join.
- [x] Kaggle submission was not performed and is machine-recorded.

## Risks

- Current-field causal attribution remains inconclusive because the safe cohort is metadata-only; the report does not overstate that association.
- The public-capital proxy excludes opponent-private inventory by design and is an exposure metric, not a full opponent net-worth identity.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

# Solo Worker Report — SOT-2908

## Summary

Evaluated the independent step-0 five-WHEAT market lead on an entity/episode/seed/time-disjoint,
same-seed both-seat screen→confirm panel. The screen passed before confirm was opened, confirm also
passed, and the candidate was promoted by setting `PUBLIC_STEP0_WHEAT_MARKET_LEAD = True`.
`cv_representative=false` remains explicit and no Kaggle submission was performed.

## Changed Files

- `main.py` — promoted the candidate and kept it exact-control outside the Kaggle runtime trigger.
- `scripts/measure_public_step0_wheat_sealed_panel.py` — deterministic sealed A/B and strict gate.
- `scripts/evaluate.py` — modeled `BUY_PRODUCT` in the offline simulator.
- `tests/test_evaluate.py` — promotion, fingerprint, firing, and invariance coverage.
- `docs/measurements/SOT-2905/SOT-2908-public-step0-wheat-sealed-panel.{json,md}` — evidence.
- `docs/ai/experiment_ledger.jsonl` — promoted experiment entry.
- `submission.tar.gz` — rebuilt promoted archive.

## Verification

- Python compile: PASS.
- Unit tests: PASS, 135/135.
- Deterministic screen reproduction: PASS.
- Screen: 4 A/B rows; mean margin +2214.25, lower-tail/worst +7, firing 4/4.
- Confirm: 4 A/B rows; mean/lower-tail/worst margin +8, firing 4/4.
- Runtime ratios: screen 1.01x, confirm 1.00x; threshold 2x.
- Runtime/action contract: all DONE/DONE; invalid actions and contract violations 0.
- Effective config fingerprint: `19975ef95f643f29bd646e8055f2e0527a02811158dcfe556375e6b0f35b387d`.
- Submission archive/entrypoint compatibility: PASS.
- `git diff --check`: PASS.
- npm gates: N/A; Python-only repository with no `package.json`.
- Kaggle submission: NOT PERFORMED.

## Acceptance Criteria

- [x] Screen/confirm are disjoint by entity, episode, seed, and time.
- [x] Same-seed both-seat rank/tail gate is recorded.
- [x] Firing evidence supports a promoted decision.
- [x] Effective flag/fingerprint and artifact change are recorded.
- [x] No Kaggle submission occurred.

## Risks

The local panel is not representative of live leaderboard CV. Screen productive completion decreased
by 26 actions despite positive rank-neutral margin/tail results; this is disclosed in the measurement.

## Linear Report: POSTED
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

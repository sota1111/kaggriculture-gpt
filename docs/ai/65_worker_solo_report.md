# Solo Worker Report — SOT-2853

## Summary

Integrated the SOT-2851 public-state capacity oracle with the SOT-2852 dispatcher in a sealed, leak-free promotion panel. The same-seed/both-seat screen produced direct intervention evidence and improved rank/margin while reducing travel, but productive density regressed and repair work increased. The candidate was therefore rejected, confirm remained sealed, and the dispatcher stays default-OFF. PR #69 merged as `4b11fe3`; no Kaggle submission occurred.

## Changed Files

- `scripts/measure_capacity_dispatcher_sealed_panel.py` — sealed holdout, deterministic rerun, screen/confirm, decision, fingerprint, and contract gate.
- `tests/test_evaluate.py` — rejection evidence and fail-closed oracle coverage.
- `docs/measurements/SOT-2850/SOT-2853-capacity-dispatcher-sealed-panel.json` — complete decision evidence.
- `docs/ai/experiment_ledger.jsonl` — cycle-7 rejected axis record.

## Verification

- Python compileall: PASS.
- Unit tests: 107/107 PASS.
- GitHub CI submission and GitGuardian: PASS.
- Submission contract and exec compatibility: PASS.
- Diff review and mergeability: PASS; no conflict.
- npm lint/typecheck/e2e: N/A (Python-only repository; no package.json/e2e configuration).

## Acceptance Criteria

- [x] Same-seed/both-seat direct A/B screen saved.
- [x] Independent confirm is consumed only after a passing screen; it remained untouched after rejection.
- [x] Rank/margin/tails and productive/travel/repair metrics drive the decision.
- [x] Rejected result and direct firing evidence appended to the ledger.
- [x] Candidate remains default-OFF; no promoted artifact was generated.
- [x] Submission contract and exec compatibility pass.
- [x] No Kaggle submission was performed.

## Risks

The candidate improved mean rank by 1, paired mean/lower-tail/worst margin by +110, and reduced travel by 344, but productive density fell by 0.004156 and 52 repair interventions were added. The disabled implementation remains only as an auditable ablation.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

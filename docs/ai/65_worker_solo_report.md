# Solo Worker Report — SOT-2906

## Summary

Implemented and ran a current-public first-action-family divergence screen. The pinned Rayk C95 and
Boatlee V16-RC5 agents were evaluated against the current champion on two disjoint seeds with both seat
assignments. All four runs identified `market` as the first emitted divergent family at step 0.

## Changed Files

- `scripts/measure_current_public_divergence.py` — provenance validation, leak-free screen, family telemetry.
- `tests/fixtures/current_public_divergence.json` — pinned screen and unopened confirm manifest.
- `tests/test_evaluate.py` — boundary, family, and first-divergence tests.
- `docs/measurements/SOT-2905/SOT-2906-current-public-divergence.{json,md}` — evidence and reproduction.
- `docs/ai/experiment_ledger.jsonl` — promoted evaluation-axis entry.
- `docs/ai/linear/SOT-2906.md` — local lifecycle record.

## Verification

- Python compile: PASS.
- Unit tests: PASS, 132/132.
- Deterministic full screen rerun: PASS; byte-identical SHA-256 `a3892562...d832d975`.
- Runtime/action contract: PASS; 4/4 episodes ended `DONE` for both agents.
- Submission contract for unchanged `main.py`: PASS.
- `git diff --check`: PASS.
- npm lint/typecheck/test/e2e: N/A; this repository is Python-only and has no `package.json`.
- Kaggle submission: NOT PERFORMED.

## Acceptance Criteria

- [x] Public-solution and official-baseline provenance is URL/version/hash pinned.
- [x] Same-seed/both-seat screen is reproducible.
- [x] First fired divergence is identified and all fired/unfired families are recorded.
- [x] Confirm cohort is reserved unopened.
- [x] No Kaggle submission occurred.

## Risks

The first divergence is observational attribution, not causal uplift. The conditional port and sealed
promotion decision remain scoped to SOT-2907 and SOT-2908. Confirm identities were not consumed.

## Linear Report: PENDING
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

# Solo Worker Report — SOT-3002

## Summary

Pinned and transiently reproduced the exact V16-RC5 whole agent. Because the
notebook declares no license, the source and executable were not redistributed;
the durable candidate descriptor is fail-closed and non-promotable. The exact
hash-pinned source nevertheless passed isolated screen/confirm runtime checks.

## Changed Files

- `candidates/v16_rc5/` — provenance, license boundary, and usage notes
- `scripts/measure_v16_rc5_whole_agent.py` — transient extractor and evaluator
- `tests/test_measure_v16_rc5.py` — hash drift and fail-closed tests
- `docs/measurements/SOT-3002/v16-rc5-screen-confirm.json` — sealed evidence
- `docs/ai/experiment_ledger.jsonl` — inconclusive result with evidence
- `docs/ai/linear/SOT-3002.md` — local lifecycle note

## Verification

- Exact notebook/agent hashes: PASS
- Screen: 2/2 wins, both seats, mean/worst +176705
- Confirm: 4/4 wins, isolated lineage/episode/seed/seat/time, mean +176007.75
- Runtime: 6/6 DONE/DONE, 720 frames, zero invalid/runtime errors
- Firing: premium lead 214; WEED recovery 3
- Full unit suite: 243 passed, 2 optional skips
- npm lint/typecheck/test/e2e: N/A (no `package.json`)
- `py_compile`, focused tests, `git diff --check`: PASS
- Incumbent `main.py` SHA-256 unchanged; no Kaggle submission

## Acceptance Criteria

- [x] provenance/license/hash and portability decision recorded
- [x] exact independent agent proved stdlib/offline/exec-compatible transiently; redistribution failed closed
- [x] screen and isolated confirm results plus firing evidence saved
- [x] ledger appended as `inconclusive` with direct evidence
- [x] Kaggle submission not performed

## Risks

Local proxy results are not live-field promotion evidence. Unknown redistribution
rights prevent committing or promoting the exact executable.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

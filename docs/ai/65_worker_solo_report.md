# Solo Worker Report — SOT-2982

## Summary

- V111 notebook version 1, notebook SHA-256, and emitted agent SHA-256 were pinned.
- Because the acquired metadata/body declares no license, upstream executable and opaque replay-derived action table were not redistributed.
- Added a default-off, champion-independent clean-room whole-agent package on the attributed MIT lonespear foundation.
- Completed same-seed/both-seat screen and opponent/episode/seed/seat/time-separated confirm.
- Candidate was rejected: screen mean-margin delta -91,990.5 and tail delta -74,376; confirm mean-margin delta -88,756.5 and tail delta -106,669.
- No Kaggle submission was performed.

## Changed Files

- `candidates/v111-economic-core/*` — clean-room overlay, provenance, attribution, usage notes.
- `scripts/package_v111_economic_core.py` — deterministic standalone artifact builder.
- `scripts/measure_v111_economic_core.py` — sealed screen/confirm A/B harness and firing evidence.
- `tests/fixtures/v111_economic_core.json` — pre-registered disjoint panel.
- `tests/test_v111_economic_core.py` — provenance, packaging, and evidence assertions.
- `docs/measurements/SOT-2981/SOT-2982-v111-economic-core.json` — complete evaluation evidence.
- `docs/ai/experiment_ledger.jsonl` — rejected-axis record.

## Verification

- `python3 scripts/measure_v111_economic_core.py` — PASS; rejected-same-seed-ab; all 16 A/B episodes DONE/DONE at 720 steps.
- `python3 -m compileall -q ...` — PASS.
- `python3 -m unittest discover -s tests` — PASS, 221 tests, 2 skipped optional checkouts.
- `git diff --check` — PASS.
- npm lint/typecheck/test/e2e — N/A; repository has no `package.json` and uses Python gates.

## Acceptance Criteria

- [x] Source URL/license/hash/provenance fixed; missing license is explicitly fail-closed.
- [x] Candidate builds as one independent offline agent and never depends on `main.py`.
- [x] Same-seed/both-seat screen and sealed confirm completed.
- [x] Ledger includes the evidence-backed rejected result.
- [x] No Kaggle submission performed.

## Risks

- The exact public route could not be redistributed due to absent license metadata; the clean-room direction is intentionally narrower than the opaque artifact.
- Rejection applies to this clean-room 8C4S/premium-order implementation, not to inaccessible upstream code under a future explicit license.

## Linear Report: PENDING
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

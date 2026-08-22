# Solo Worker Report — SOT-2958

## Summary

Recovered the exact Apache-2.0 Barnyard Economist v5 Version 4 output and
registered it as an independent, default-OFF whole-agent hedge. The unchanged
champion and candidate were evaluated on identical both-seat screen identities
and a disjoint chronological confirm cohort. No Kaggle submission was made.

## Changed Files

- `candidates/barnyard-economist-v5/` — exact agent, Apache license, provenance, effective config, and attribution
- `scripts/measure_barnyard_economist.py` — reproducible paired screen/confirm evaluator and gate
- `tests/fixtures/barnyard_economist.json` — registered opponent/seed/seat/time holdout
- `tests/test_barnyard_economist.py` — provenance, portability, contract, and evidence tests
- `docs/measurements/SOT-2957/SOT-2958-barnyard-economist.json` — real paired results and fingerprints
- `docs/ai/experiment_ledger.jsonl` — cycle-4 axis result

## Verification

- Exact source: Kaggle Version 4 / scriptVersionId `339537120`, 26,394 bytes, SHA-256 `26311e7c17449c862c0a2edc5b00224f81f0580aa7f4b8d78073b4026f7d814a`
- License: Apache-2.0 vendored and hash-verified
- Portability: stdlib-only imports; entrypoint and submission contract PASS
- Screen: mean-margin delta `+87,198`; p20/worst delta `+69,483`; gate PASS
- Confirm: mean-margin delta `+110,534.25`; p20/worst delta `+129,304`; gate PASS
- Rank: both candidate and champion remained rank 2 in all registered matches
- Runtime: all evaluated episodes reached `DONE/DONE` at 720 steps
- Tests: 180 passed, 2 expected skips; candidate-specific 2/2 passed; compileall PASS
- npm lint/typecheck/test/e2e: N/A (repository has no `package.json`; Python gates apply)
- Champion `main.py`: SHA-256 `0c10cbf2a2c806f87c0d04257c5f90c87074dce26566d6450fc8276a5d48a14f`, unchanged

## Acceptance Criteria

- [x] Exact whole-agent source, Apache-2.0 license, and effective config recorded
- [x] Independent same-seed/both-seat screen and disjoint confirm recorded with rank/margin/tail/worst
- [x] Two-signal and tail-nonregression gate applied without using notebook grid-search/LB as evidence
- [x] Action-family firing fingerprint differs from the champion
- [x] stdlib/offline and agent entrypoint/submission contracts pass
- [x] No Kaggle submission; champion runtime and submission artifact remain unchanged

## Risks

- Candidate and champion both lost every registered public-opponent match; this is a relative hedge promotion, not evidence of leaderboard-rank superiority.
- The candidate is intentionally default-OFF and was not integrated into `main.py`.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

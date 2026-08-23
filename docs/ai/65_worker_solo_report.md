# Solo Worker Report — SOT-3033

## Summary

Pinned Kaggle kernel 129971739 / script version 341206423, notebook SHA-256
`e28aa997dc5317cad8e2a8ee5887efa7c12c40fc17e41af366f2723f29f21406`,
embedded artifact SHA-256
`9bdfbafb6755067182d88ce594fd46fb1d712713ffd6931e83d5d50e84bc6fb2`,
and Apache-2.0 provenance. The notebook declares its 719-action backbone was
reconstructed from a public replay, so the exact artifact was kept fetch-only.

Built an independent clean-room whole-agent package from the separately
Apache-2.0 Agent Builder foundation, retaining only v25's portable sheep-first
basin and public-market SELL-slot ordering. Candidate SHA-256 is
`5db1a9e17227ee7b049bafd12c0d758b9a210df1b9c1ef2124767e583fcbfc02`.
The incumbent and submission archive were not modified; no Kaggle submission
was made.

## Changed Files

- `candidates/v25-strict-future-cleanroom/` — independent artifact, policy, provenance, license, and documentation
- `scripts/package_v25_strict_future.py` — deterministic package builder
- `scripts/measure_v25_strict_future.py` — static audit and direct screen/confirm runner
- `tests/fixtures/v25_strict_future.json` — preregistered disjoint panels
- `tests/test_v25_strict_future.py` — provenance, independence, contract, and evidence gates
- `docs/measurements/SOT-3033/v25-screen-confirm.json` — complete measured evidence
- `docs/ai/experiment_ledger.jsonl` — promoted result with qualification

## Verification

- Targeted unit tests: 3 passed
- Full suite: 288 passed, 2 skipped (upstream checkout unavailable)
- Python compileall: passed
- Submission contract validator: passed
- Static audit: longest literal sequence 9; no large action lookup, network import, or sensitive runtime identity tokens
- Screen: all four candidate episodes DONE, invalid actions 0; foundation-relative mean-margin delta +19,344, worst-margin delta +856
- Sealed confirm: opponent/lineage/episode/seed/seat/time disjoint; all four candidate episodes DONE, invalid actions 0; foundation-relative mean-margin delta +13,523.75, worst-margin delta +13,251
- npm lint/typecheck/test/e2e: N/A (repository has no package.json; Python gates above are canonical)

## Acceptance Criteria

- [x] Provenance and artifact hashes recorded
- [x] Independent whole-agent screen and sealed confirm completed
- [x] Experiment ledger records `promoted` with direct A/B evidence and absolute-performance qualification
- [x] Kaggle submission not performed

## Risks

Promotion is relative to the independent foundation. The candidate lost all
four absolute confirm matchups despite improving every aggregate margin gate,
so it is retained as a hedge and does not replace the incumbent.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

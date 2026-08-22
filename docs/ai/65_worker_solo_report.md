# Solo Worker Report — SOT-3003

## Summary

Verified the exact hash-pinned v27 Strict-Future whole agent transiently. The notebook/output hashes, 20,813-byte stdlib artifact, single 719-step route, both-seat runtime contract, chronological screen/confirm isolation, and actor/market/SELL-slot firing all pass. Because upstream declares no license, the exact bytes are not redistributed and the evidence remains inconclusive; the incumbent and submission archive are unchanged and no Kaggle submission was made.

## Changed Files

- `candidates/kaito-v27-strict-future/` — fail-closed provenance manifest and boundary.
- `scripts/measure_kaito_v27_strict_future.py` — transient acquisition and chronological evaluation.
- `tests/fixtures/kaito_v27_strict_future.json` / `tests/test_kaito_v27_strict_future.py` — frozen panel and regression tests.
- `docs/measurements/SOT-3003/v27-strict-future-screen-confirm.json` — measured evidence.
- `docs/ai/experiment_ledger.jsonl` — evidence-qualified conclusion.

## Verification

- Pinned notebook and agent hashes: PASS.
- Transient whole-agent measurement: screen/confirm PASS; decision inconclusive.
- Targeted tests: 2 passed.
- Full suite: 249 passed, 2 skipped.
- Production `main.py` contract: PASS.
- Kaggle submission: NOT_PERFORMED.

## Acceptance Criteria

- [x] Provenance/license/hashes and structural difference from v19/v39 recorded.
- [x] Exact whole agent verified stdlib/offline/exec compatible; redistribution fails closed.
- [x] Same-seed/both-seat screen and later separated confirm with firing evidence saved.
- [x] Experiment ledger appended with evidence-qualified inconclusive result.
- [x] Kaggle submission not performed.

## Risks

Local proxies were strongly positive, but exact redistribution is unlicensed and prior evidence documents local-to-live drift. This candidate must not be promoted from these results.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

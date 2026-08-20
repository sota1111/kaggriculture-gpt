# Solo Worker Report — SOT-2820

## Summary

Real Kaggriculture環境で、commit/hash/license固定した公開artifactとのslot-swapped closed-loop holdoutを実装した。8 matchは全て720 states・DONE/DONE・stderr/errorsなしで完走し、再実行もbyte-identical。championは0-8だったため評価oracleを昇格し、runtime policyは変更せずKaggle提出も行っていない。

## Changed Files

- `scripts/measure_public_closed_loop_holdout.py` — provenance検証・fetch・live league
- `tests/fixtures/public_closed_loop_holdout.json` — immutable artifact/panel manifest
- `tests/test_evaluate.py` — drift/leakage fail-closed tests
- `docs/measurements/SOT-2819/SOT-2820-closed-loop-holdout.json` — per-match evidence
- `docs/ai/experiment_ledger.jsonl` — promoted oracle entry
- `docs/ai/linear/SOT-2820.md` — acceptance record

## Verification

- Python compile: PASS
- Unit tests: 72/72 PASS
- Manifest drift/leakage fail-closed tests: PASS
- Live league: 8/8 matches, 720 states, DONE/DONE, stderr/errors empty
- Deterministic rerun: byte-identical PASS
- Submission contract and archive: PASS
- npm lint/typecheck/e2e: N/A（package.json/browser surfaceなし）
- Kaggle submission: NOT PERFORMED

## Acceptance Criteria

- [x] hash/license/commit-pinned public artifact manifest
- [x] entity/seed/time-isolated screen and confirm
- [x] both-seat champion baseline and raw per-match evidence
- [x] no replay bytes, credentials, or weights committed
- [x] no Kaggle submission performed

## Risks

- Championの0-8は重大なclosed-loop transfer driftを示す。recorded-action replayをlive勝率として扱わず、本leagueを後続policyの昇格gateに使う必要がある。

## Linear Report: PENDING

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

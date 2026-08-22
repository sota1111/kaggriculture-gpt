# Solo Worker Report — SOT-3008

## Summary

公式 `kaggle-environments==1.32.7` の engine constants/functions から経済 oracle snapshot を再構築した。engine／AGENTS／license の hash と version を固定し、crop・animal・market・town・labor・land・shed・最終 step の恒等式を offline で再生成できる。incumbent／C95／Hamburger を screen と分離 confirm の同一 seed／both-seat で実測し、entity/opponent/lineage/seed/seat/time/action-family 別の計画値・実現値乖離を 730 件記録した。Kaggle 提出は行っていない。

## Changed Files

- `scripts/evaluation/economic_oracle.py` / snapshot — engine-derived formulas and fail-closed pinning
- `scripts/build_economic_oracle_snapshot.py` — offline reproduction/check command
- `scripts/measure_engine_economic_oracle.py` — paired trajectory-gap measurement
- `tests/evaluation/test_economic_oracle.py` / `test_measure_engine_economic_oracle.py` — identity/property/drift/split tests
- `docs/measurements/SOT-3008/engine-economic-oracle.json` — 12-game evidence
- `docs/ai/experiment_ledger.jsonl` — cycle-4 inconclusive axis record

## Verification

- Python compileall: PASS
- Unit tests: 267 PASS, 2 existing optional skips
- Snapshot regeneration check: PASS
- 12/12 official-engine episodes: 720 steps, DONE/DONE
- `main.py` / `submission.tar.gz`: unchanged
- npm lint/typecheck/e2e: N/A (Python-only repository; no package.json/UI)

## Acceptance Criteria

- [x] engine/source version/hash/license and derived formulas recorded
- [x] oracle reproduces offline without replay bytes or credentials
- [x] same-seed screen and isolated confirm trajectory-gap report recorded
- [x] engine/version/hash/identity mismatch fails closed
- [x] no Kaggle submission

## Risks

The notebook declares no redistribution license, so it is provenance/design-only and no code was copied. The measurements validate attribution, not candidate promotion; ledger result is correctly `inconclusive`.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

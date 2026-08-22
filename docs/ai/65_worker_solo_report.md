# Solo Worker Report — SOT-2973

## Summary

Apache-2.0 公開 notebook Soil Remembers Rain V26-H を、最新 script version 344052698 から byte-identical な独立 candidate として取得・包装した。same-seed/both-seat screen と opponent/episode/seed/seat/time 分離 sealed confirm はともに 4/4 勝で通過し、候補を台帳上 promoted とした。既存 `main.py` は変更せず hedge として保持し、Kaggle 提出は行っていない。

## Changed Files

- `candidates/soil-remembers-rain/` — exact agent, provenance, Apache-2.0 license, notice, reproduction guide
- `scripts/measure_soil_remembers_rain.py` — preregistered screen/confirm and intervention evidence
- `docs/measurements/SOT-2971/SOT-2973-soil-remembers-rain.json` — sealed measurement rows and decision
- `docs/ai/experiment_ledger.jsonl` — promoted axis with evidence
- `tests/test_soil_remembers_rain.py` — provenance, contract, panel and hedge assertions
- `docs/ai/linear/SOT-2973.md` — local issue record

## Commands Run

- Kaggle authenticated kernels pull/output — PASS
- `python3 scripts/measure_soil_remembers_rain.py` — PASS (`screen_gate=PASS`, `decision=promoted`)
- `python3 scripts/validate_submission.py candidates/soil-remembers-rain/agent.py` — PASS
- `python3 -m compileall -q main.py candidates scripts tests` — PASS
- `python3 -m unittest discover -s tests -v` — PASS (210 passed, 2 skipped)
- npm lint/typecheck/test/e2e — N/A (repository has no `package.json`; engine panel is the applicable e2e)

## Acceptance Criteria

- [x] Source version/hash/license/portability pinned
- [x] Independent package is callable and submission-contract compatible
- [x] Screen and sealed confirm record both-seat, split-isolated, firing/intervention evidence
- [x] Experiment ledger records an evidence-backed promoted decision

## Risks

- Local engine panels are transfer proxies; no Kaggle submission was authorized or performed.
- Two unrelated upstream tests skip when an optional exact V7 checkout is absent.

## Linear Report: PENDING
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

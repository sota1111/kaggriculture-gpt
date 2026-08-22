# Solo Worker Report — SOT-2965

## Summary

Audited the Kaggle API snapshot and transient embedded whole-agent, recorded exact notebook/agent
hashes and runtime boundaries, and evaluated it with a disjoint same-seed/both-seat screen→confirm
panel. The empirical performance gate passed, but the final portability decision is rejected because
no redistribution license is declared. No source agent was committed; the champion remains unchanged.

## Changed Files

- `candidates/pure-architecture-2600/` — fail-closed provenance descriptor and boundary note
- `tests/fixtures/pure_architecture_2600.json` — independent screen/confirm identities
- `scripts/measure_pure_architecture_2600.py` — transient acquisition, hash audit, and evaluation
- `tests/test_pure_architecture_2600.py` — provenance, contract, tail, and hedge assertions
- `docs/measurements/SOT-2962/SOT-2965-pure-architecture-2600.json` — reproducible evidence
- `docs/ai/experiment_ledger.jsonl` — rejected portability-axis result

## Commands Run

- Kaggle API `kernels pull` / `kernels output` — source snapshot acquired; no output artifact published
- measurement command — PASS; screen and confirm gates passed; final portability decision rejected
- deterministic reruns — matching non-timing evidence hash before final decision encoding
- `python -m compileall -q scripts tests` — PASS
- `python -m unittest discover -s tests -v` — PASS, 195 tests, 2 expected skips
- npm lint/typecheck/test/e2e — N/A, repository has no `package.json`
- `git diff --check` — PASS

## Acceptance Criteria

- [x] License/source/hash/runtime boundary recorded fail-closed
- [x] Whole-agent evaluated transiently through an independent fixture without redistribution
- [x] Both-seat screen/confirm, rank, relative margin, p20/worst, and deterministic evidence recorded
- [x] Existing champion and archive hashes match `origin/main`
- [x] Evidence-aligned rejected decision appended to the experiment ledger

## Risks

- The candidate cannot be redistributed or adopted until the author supplies a compatible license.
- Public “2600+” wording was deliberately excluded from evidence.

## Linear Report: PENDING
## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

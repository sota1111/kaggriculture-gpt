# Solo Worker Report — SOT-2938

## Summary

Implemented a fresh closed-loop private-proxy oracle for the current champion. The oracle enforces opponent-lineage, episode, seed, and chronological time-slice separation between screen and confirm, pairs every identity across both seats, aggregates margin/rank/p20/worst by distribution, and reports confirm-minus-screen transfer stability. Candidate, opponent, engine, seed panel, and manifest hashes are pinned. Open-loop replay is labelled separately and excluded from transfer-trust.

## Changed Files

- `scripts/measure_private_proxy_oracle.py` — validation, engine execution, aggregation, provenance, and transfer-trust report.
- `tests/fixtures/private_proxy_oracle.json` — four pinned opponent lineages and disjoint both-seat screen/confirm identities.
- `tests/test_evaluate.py` — overlap rejection, both-seat coverage, and deterministic distribution aggregation tests.
- `docs/measurements/SOT-2934/SOT-2938-private-proxy-oracle.json` — measured champion artifact.
- `docs/ai/experiment_ledger.jsonl` — promoted oracle-axis result.
- `README.md` — reproduction and evidence-boundary documentation.
- `docs/ai/linear/SOT-2938.md` — issue-local lifecycle note.

## Commands Run

- `python3 -m compileall -q main.py scripts` — PASS.
- `python3 -m unittest discover -s tests -v` — PASS, 141/141.
- `bash scripts/build_submission.sh` and archive entry check — PASS.
- `.venv/bin/python scripts/measure_private_proxy_oracle.py` twice — PASS; byte-identical SHA-256 `27d770e2b9c29a0ca8373f25abec478ee0c9f72d426d5df1d4866fbe6c17a273`.
- `git diff --check` — PASS.
- npm lint/typecheck/test/e2e — N/A; repository has no package manifest. Python compile/unit, submission contract, and real Kaggle-engine closed-loop runs are the repository-equivalent gates.

## Acceptance Criteria

- [x] entity/opponent lineage, episode, seed, and time-slice overlap are zero; seat leakage is controlled with complete same-identity both-seat pairs.
- [x] both-seat closed-loop margin, rank, p20/worst tail, distribution aggregates, and transfer-trust are output.
- [x] candidate/opponent/engine/seed-panel/manifest provenance and hashes are recorded; open-loop and closed-loop metrics are separate; screen/confirm policy is explicit.
- [x] repository-equivalent compile, 141 tests, submission contract, real-engine run, deterministic rerun, and diff checks pass.
- [x] `kaggle_submission` is `NOT_PERFORMED`.

## Risks

- The champion ranked second in all eight proxy episodes. This is evidence about the current proxy baseline, not a policy regression introduced by this evaluation-only change.
- `cv_representative=false` remains: transfer stability is a private proxy and does not claim live leaderboard calibration.

## Linear Report: PENDING

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

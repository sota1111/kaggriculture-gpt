# Solo Worker Report

## Summary

Implemented a hash-pinned Adaptive Replay common oracle and ran a fresh sealed closed-loop tournament over V111, R5A, Conditional Memory, and the old champion. The manifest fails closed on opponent/lineage/episode/seed/seat-group/time overlap, keeps replay bytes local-only, and separates open-loop diagnostics from closed-loop strength.

## Changed Files

- `scripts/measure_adaptive_replay_portfolio.py` — validation, artifact freezing, tournament, robust aggregation and selection
- `tests/fixtures/adaptive_replay_portfolio.json` — pre-registered unused confirm identities and leakage boundary
- `tests/test_adaptive_replay_portfolio.py` — overlap fail-closed and committed-result tests
- `docs/measurements/SOT-2981/SOT-2984-adaptive-replay-portfolio.json` — 16-match sealed evidence
- `docs/ai/experiment_ledger.jsonl` — evidence-backed promoted portfolio hedge result
- `docs/ai/linear/SOT-2984.md` — issue tracking and acceptance record

## Commands Run

- `python3 scripts/measure_adaptive_replay_portfolio.py` — PASS; 16 matches completed
- `python3 -m compileall -q main.py scripts` — PASS
- `python3 -m unittest discover -s tests -v` — PASS; 229 tests, 2 skipped
- `bash scripts/build_submission.sh` and archive contract check — PASS; generated archive reverted
- `git diff --check` — PASS

## Acceptance Criteria

- [x] provenance, immutable hashes, and local-only replay boundary fixed
- [x] all four artifacts compared on a common sealed panel
- [x] opponent/lineage/episode/seed/seat/time leakage checks passed
- [x] tail, rank stability, and matchup spread saved
- [x] portfolio evidence appended to ledger
- [x] no Kaggle submission; champion and archive unchanged

## Risks

All four policies lost both unseen opponent matchups, and mean rank was tied at 2.0. Conditional Memory leads only on relative margin/tail/spread under a non-representative CV proxy, so it is retained as a portfolio hedge rather than installed as the production champion.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

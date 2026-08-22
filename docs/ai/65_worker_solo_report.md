# Solo Worker Report — SOT-2989

## Summary

Pinned the public Reactive Optimal Task kernel and its outputs, recorded the undeclared-license boundary, implemented an independent standard-library clean-room whole agent, and completed same-seed/both-seat screen plus fully separated confirm. The candidate passed the tail-sensitive hedge gate and is retained default-OFF; the prior champion remains unchanged and no Kaggle submission was made.

## Changed Files

- `candidates/reactive-optimal-task/agent.py` / `source.json` — clean-room agent and provenance boundary.
- `scripts/measure_reactive_optimal_task.py` — contract, intervention, screen, and confirm evaluator.
- `tests/fixtures/reactive_optimal_task.json` / `tests/test_reactive_optimal_task.py` — sealed identities and focused tests.
- `docs/measurements/SOT-2989/SOT-2989-reactive-optimal-task.json` — reproducible evidence.
- `docs/ai/experiment_ledger.jsonl`, `docs/ai/linear/SOT-2989.md`, `README.md` — decision and usage records.

## Verification

- Python compile: PASS.
- Full unit suite: 234 PASS, 2 environment-dependent skips.
- Submission contract and existing single-root archive integrity: PASS.
- Official-engine evaluation: 16/16 champion/candidate episodes ended `DONE/DONE` at 720 steps, within timeout, with 0 invalid actions.
- Screen candidate vs champion: mean-margin delta +24574.75; p20/worst +27458; equal mean rank 2.0; gate PASS.
- Confirm candidate vs champion: mean-margin delta -3193.5; p20/worst +5390; equal mean rank 2.0; two-signal non-regressing-tail gate PASS.
- Intervention log: 5752 calls; 6432 assigned tasks; action-family fingerprint diverged from champion.
- Kaggle submission: NOT_PERFORMED.

## Acceptance Criteria

- [x] Source/version/license/hash and clean-room boundary recorded.
- [x] Independent agent runs and records task-selection interventions.
- [x] Same-seed/both-seat screen and separated confirm are saved.
- [x] Evidence-backed decision appended to the experiment ledger.
- [x] No Kaggle submission; old champion remains an independent hedge.

## Risks

Mean rank remained 2.0 in both panels and confirm mean margin regressed slightly. Promotion is limited to a structurally independent default-OFF portfolio hedge; it is not a champion replacement or live-field claim.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

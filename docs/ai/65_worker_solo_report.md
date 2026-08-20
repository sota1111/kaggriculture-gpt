# Worker Report — SOT-2825

## Summary

Added a reproducible sealed closed-loop gate for the distilled compact policy. Four unseen same-seed/both-seat A/B matches completed successfully. The candidate preserved rank and improved relative margin, but regressed own reward by 1,194 in every match, so the strict gate rejected it, skipped independent confirm, and retained `COMPACT_REPLAY_POLICY=false`.

## Changed Files

- `scripts/measure_compact_policy_sealed_gate.py` — sealed panel, strict rank/reward/tail/runtime/contract gate, fingerprint and evidence output
- `tests/test_evaluate.py` — isolation, fail-closed manifest, and reward non-regression coverage
- `docs/measurements/SOT-2823/SOT-2825-compact-policy-sealed-gate.json` — complete match evidence
- `docs/ai/experiment_ledger.jsonl` — one cycle-3 rejected-axis entry
- `docs/ai/linear/SOT-2825.md` — lifecycle and decision note
- `docs/ai/70_final_report.md` — acceptance summary

## Commands Run

- `.venv/bin/python scripts/measure_compact_policy_sealed_gate.py` twice — PASS; deterministic excluding runtime timing
- `.venv/bin/python -m unittest discover -s tests -v` — 84/84 PASS
- `.venv/bin/python -m py_compile main.py scripts/*.py tests/test_evaluate.py` — PASS
- `bash scripts/build_submission.sh` and submission validation — PASS; one gzip member containing only `main.py`

## Acceptance Criteria

- [x] Unseen closed-loop both-seat direct A/B completed on opponent/seed/time-disjoint identities
- [x] Rank, reward, tails, runtime, and contract gate recorded
- [x] Land/labor firing evidence corresponds to the effective-config fingerprint
- [x] Disabled decision is reproducible; independent confirm skipped after strict screen failure
- [x] Rejection has same-seed direct A/B plus firing evidence
- [x] Exactly one JSONL ledger entry appended

## Risks

The candidate improves relative margin while reducing its own reward; the strict gate intentionally prioritizes non-regression across both. No third cohort was consumed after screen failure.

## Linear Report

Completion Report and PR merge sync posted successfully; Issue moved to In Review.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

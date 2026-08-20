# Worker Report — SOT-2826

## Summary

Distilled a portable state-conditioned land/labor threshold table from the hash-pinned SOT-2824 winner-only screen split. The independent component and counters are auditable and stdlib-only. Its same-seed/both-seat screen ablation fired every adopted branch without invalid actions, but materially regressed reward and tail margin, so the strict gate rejected it, confirm was skipped, and `COMPACT_REPLAY_POLICY` remains disabled.

## Changed Files

- `main.py` / `submission.tar.gz` — independent compact policy flag, embedded constants, and land/labor counters
- `scripts/distill_compact_replay_policy.py` — deterministic screen-only reproduction
- `scripts/measure_compact_replay_policy.py` — targeted firing trace and direct closed-loop screen A/B
- `tests/test_evaluate.py` — provenance, independence, and branch-firing checks
- `docs/measurements/SOT-2823/` — distillation and ablation evidence
- `docs/ai/experiment_ledger.jsonl` — one rejected cycle-3 axis entry

## Verification

- Python compile: PASS
- Unit tests: 81/81 PASS
- Teacher reproduction: PASS; 2,160 screen rows, dataset SHA-256 `c2807cd6f38f5a69201939f973114310e89a64dd000e34fce9bf372ba068348f`, confirm tuning rows 0
- Targeted trace: PASS; land and labor branches fired
- Direct screen A/B: REJECTED as designed; mean/lower-tail/worst margin delta `-8586.5/-14240/-14240`, mean reward delta `-1194`
- Runtime contract: PASS; zero invalid actions/contract violations
- Semantic measurement rerun: byte-equivalent after excluding runtime timing
- Submission contract/archive: PASS; one gzip member containing only `main.py`
- GitHub PR #50: mergeable, CI submission and GitGuardian checks PASS
- npm lint/typecheck/e2e: N/A (Python-only repository; closed-loop A/B replaces browser E2E)
- Kaggle submission: NOT PERFORMED

## Acceptance Criteria

- [x] Portable compact policy exists behind an independent flag
- [x] Methodology, dataset hash, split boundary, and generated constants are recorded
- [x] Standalone ablation records adopted-branch firings
- [x] Strict screen result controls retention; rejected policy remains disabled and confirm is skipped
- [x] Rejection includes direct A/B and intervention evidence
- [x] Exactly one JSONL experiment entry was appended

## Risks

The teacher's land/labor cadence does not transfer independently to the current champion. The code remains inert by default; downstream SOT-2825 can consume the evidence without treating it as a promoted candidate.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

# Solo Worker Report — SOT-3035

## Summary

Implemented a provenance-pinned, metadata-only current-field transfer oracle. The builder sorts public
episode identities chronologically before freezing screen/confirm, validates source and target hashes,
fails closed on raw replay/credential/private/action payloads, and enforces opponent/lineage/episode/
seed/time separation plus same-seed both-seat coverage for incumbent, C95, and an independent candidate.

The generated transfer-trust result rejects the evaluated ordering: C95 wins screen but does not
transfer to sealed confirm; incumbent remains the hedge. Confirm is not a selection input. No agent was
promoted and no Kaggle submission was made.

## Changed Files

- `scripts/measure_current_field_transfer_oracle.py` — chronological builder, leakage/provenance gate,
  paired rank/tail/bootstrap summaries, and drift decision.
- `tests/fixtures/current_field_transfer_manifest.json` — immutable metadata-only cohort and sources.
- `tests/test_current_field_transfer_oracle.py` — chronology, integrity, overlap, payload, seat, and
  selection-boundary regression tests.
- `docs/measurements/SOT-3035/current-field-transfer-trust.json` — generated machine-readable result.
- `docs/measurements/SOT-3035/current-field-transfer-trust.md` — provenance and trust interpretation.
- `docs/ai/experiment_ledger.jsonl` — rejected axis evidence.
- `docs/ai/linear/SOT-3035.md` — local issue tracking.

## Commands Run

- `python3 -m unittest tests.test_current_field_transfer_oracle -v` — 4 passed.
- `python3 scripts/measure_current_field_transfer_oracle.py` — validation PASS, oracle result rejected.
- `python3 -m unittest discover -s tests -v` — 282 passed, 2 skipped.
- `python3 -m compileall -q scripts tests` — pass (type/syntax gate; no project typechecker configured).
- `git diff --check` — pass.
- npm lint/typecheck/test/e2e — N/A; repository has no `package.json` and no browser surface.

## Acceptance Criteria

- [x] current-field cohort provenance is reproducible: URLs, versions, licenses, source hashes, target
  hashes, manifest hash, and regeneration command are committed.
- [x] leakage inspection passes: opponent, lineage, episode, seed, and time cohorts are disjoint;
  both seats are present; forbidden replay/credential/private/action payloads fail closed.
- [x] screen/confirm drift and rank/tail metrics are recorded in JSON and Markdown, including paired
  mean/p20/worst and bootstrap intervals.
- [x] Kaggle submission was not performed and is machine-checked.

## Risks

- Public corpus coverage is observational and not a census; this artifact measures transfer drift but
  does not claim a live win probability.
- Rejection applies to this oracle transfer ordering, not to C95 or the independent agent globally.

## Linear Report: POSTED

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

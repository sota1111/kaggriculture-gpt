# SOT-3016 — C95 exact submission readiness

Recorded at: 2026-08-22T11:53:00Z

## Immutable identity

- Candidate: `candidates/c95-high-score/agent.py`
- Candidate SHA-256: `ed8c8420514acb5a96c0d44cfd42a8786e49c7cdc01a0de61d2e6b8997dda87a` (matches `source.json`)
- Effective-config fingerprint: `cd276b276df40fdd4c0c8b855991b1f59e0c3634db997af24e5eb8b434c1d04a` (matches the promoted SOT-3004/SOT-3006 record)
- Incumbent hedge: `main.py`, SHA-256 `0c10cbf2a2c806f87c0d04257c5f90c87074dce26566d6450fc8276a5d48a14f`, unchanged
- Provenance: Kaggle kernel `129644554`, script version `340239322`, Apache-2.0; full source URL and notebook hash remain pinned in `source.json`

## Screen and confirm

The exact preregistered panel was rerun from the committed artifact. Raw evidence is in `c95-screen-confirm-rerun.json`.

- Same-seed/both-seat screen: PASS, 4/4 wins or ties, mean margin `+101521.5`, no invalid actions
- Opponent/lineage/episode/seed/seat/time-separated confirm: PASS, 2/4 wins or ties, mean margin `+7255.75`, no invalid actions
- Confirm direct A/B delta versus incumbent: mean margin `+163872.25`, p20/worst margin `+156084.0`
- Candidate action traces exactly match the prior sealed run for all eight screen/confirm games, establishing deterministic behavior under the fixed panel
- All 16 candidate/incumbent games reached `DONE` at 720 steps; candidate maximum runtime was `3.091s` in screen and `3.070s` in confirm

## Submission contract and packaging

- `scripts/validate_submission.py` on a temporary byte-identical `main.py`: PASS
- Python compile/exec: PASS; callable `agent` is the final runtime entrypoint
- Imports are standard-library-only: `copy`, `json`
- Fresh temporary archive contains exactly `main.py`
- Extracted archive member SHA-256: `ed8c8420514acb5a96c0d44cfd42a8786e49c7cdc01a0de61d2e6b8997dda87a`
- No external replay bytes, credentials, weights, network access, or runtime dependencies are packaged
- Kaggle submission: **NOT_PERFORMED**

## Decision

`promoted`: the artifact remains submission-ready under the immutable identity and effective configuration. This is a readiness revalidation only; it does not replace `main.py` or `submission.tar.gz`, partially transplant C95, tune it, or submit it to Kaggle.

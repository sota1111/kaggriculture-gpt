# SOT-2859 layout-aware sealed promotion decision

The panel is fixed in `tests/fixtures/layout_aware_sealed_panel.json`. Its screen cohort uses COK V7
and lonespear V23, which do not overlap the lonespear V17/V18 screen used by SOT-2861. The confirm
cohort fixes the remaining V17/V18 opponents at later, disjoint seeds and timestamps. Every opponent
is fetch-only and pinned by repository, full commit, license, and SHA-256; no replay bytes or Kaggle
credentials are committed.

Reproduce from the repository root:

```bash
python3 scripts/measure_layout_aware_sealed_panel.py
python3 scripts/validate_submission.py main.py
python3 -m unittest discover -s tests -v
```

The same-seed, both-seat screen direct A/B fired the independent layout-aware intervention. Candidate
rank improved by 1.0 and mean/lower-tail/worst margin improved by 26, with zero invalid actions or
contract violations and an acceptable runtime ratio. However, productive completion fell from 5,840
to 5,788 actions (`-52`). Because pessimistic rank/tails and productive completion are co-primary,
the screen gate rejected the candidate and did not consume the confirm cohort. The default-off
`LAYOUT_AWARE_PRODUCTION_ARCHITECTURE` configuration is retained. This is direct A/B plus firing
evidence, so `rejected` (rather than `inconclusive`) satisfies the evidence policy. No Kaggle
submission was made.

The generated JSON report records all primary metrics, productive completion, repair telemetry,
runtime, invalid actions, contract violations, screen/confirm gate state, policy/oracle/artifact/effective-
config fingerprints, and the submission/exec contract result.

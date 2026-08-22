# SOT-2960 distribution-robust closed-loop oracle

## Outcome

The evaluation oracle is promoted; no policy or submission is promoted. Eight 720-step matches executed the current champion and four immutable, licensed public agents in a live closed loop. Every matchup ran both seats at the same seed and ended `DONE/DONE`.

## Isolation and provenance

- Screen and confirm are disjoint on opponent, lineage, episode, seed, and chronological time slice. The validator fails closed on overlap or a missing seat pair.
- Opponent source URL, 40-character commit, SHA-256, license, and fetch-only status are pinned in `tests/fixtures/distribution_robust_oracle.json`.
- Confirm remained digest-sealed until screen completed, then opened only after the digest matched.
- Kaggle submission was not performed. `main.py` and `submission.tar.gz` were not changed.

## Distribution-robust result

Cluster-balanced screen mean rank/margin were 2.0 / -226,690.5; conservative p20 and worst margin were both -267,082. Confirm mean rank/margin were 2.0 / -2,234,615.5; p20 and worst were both -4,355,472. Market-regime and opponent-cluster breakdowns are retained in the JSON artifact.

Confirm-minus-screen cluster-balanced mean margin was -2,007,925 and tail/worst drift was -4,088,390, while rank remained unchanged. Stability scored 0.0 on the preregistered 0–1 scale. This demonstrates that opponent×seat×time×market distribution materially changes the proxy despite a flat rank signal.

## Open-loop boundary

The referenced replay artifact contains four recorded episodes, but recorded actions cannot respond to the candidate. Therefore comparable live rank/margin coverage is 0% and live-interaction feedback coverage is 0%; those metrics are emitted as `null`, never pooled with closed-loop outcomes, and never interpreted as parity. Open-loop replay remains stress-only evidence.

## Acceptance decision

All oracle validation and runtime checks pass. This promotes the evaluation system only. The retained champion remains unchanged as the hedge, and agent promotion is intentionally outside this issue.

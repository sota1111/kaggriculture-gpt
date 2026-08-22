# SOT-2964 live-meta transfer oracle re-anchor

## Outcome

The oracle contract is promoted; no agent is evaluated or promoted, and no Kaggle submission was made. The committed JSON contains only derived fingerprints, split identities, aggregate banks/margins, coverage diagnostics, and source hashes. Replay bytes and credentials remain outside git.

## Provenance boundary

- Kaggriculture Daily Replays notebook v19: SHA-256 `6556a8307132fe45c22cc0d3821333d028e342167dfcbd880421f9e15668fb13`.
- Kaggriculture Episodes daily snapshot (2026-08-21): `episodes.csv` SHA-256 `0069fe6ea1e8ee5c0ad0b08b12f22a655aa6e0ead10631e0beceffea9b43f534`, Apache-2.0.
- Kaggriculture replayable benchmark (45,404 matchups, 2026-08-16): `matchups_top.parquet` SHA-256 `bb94d1a5523468f83dacdaf33482648d25ab72c3ee2468fb3d9247d7cda8c11e`, CC0-1.0.
- Official `kaggle-environments==1.32.4` Kaggriculture runtime: SHA-256 `9741c0470a8db98a70644491d5121ae6295413343d1a08ef9fcee35e0b76f2c5`, Apache-2.0.

The manifest validator fails closed when URL/version/hash/license/boundary is missing, hashes are malformed, a private/future/credential/action payload appears, or validation self-play enters a strength panel.

## Split and measurement

Screen and chronological confirm are disjoint across lineage prefix, episode, resolved seed, and time cohort. Every episode retains both seats at the same seed; market regimes and 24-turn strategy fingerprints are explicit. The harness pins the current champion and an independently packaged CARE-production candidate by path and SHA-256 before measurement. Within-episode relative margin is primary, with rank, mean margin, p20, worst tail, and opponent×time×market summaries retained.

Confirm versus screen leaves mean rank/margin unchanged in this paired audit slice but worsens p20 and worst relative margin by 1,518. The conservative tail-aware stability score is recorded in the JSON. The report also emits lag-1 serial correlation, crawler-coverage correlation, effective fingerprint count, and raw row count so repeated matchup chains and crawler over-sampling cannot masquerade as independent evidence.

## Evidence limits

The corpus is a crawl, not a census. Consecutive matchups are not IID. Recorded-action replay is open-loop and cannot react to candidate actions, so it remains stress evidence rather than a live win-probability estimate. These caveats are machine-readable in the measurement artifact.

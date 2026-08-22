# SOT-2975 Adaptive Replay live-lineage transfer oracle

## Outcome

The oracle contract is promoted; no agent/champion change and no Kaggle submission were performed. The committed fixture is a synthetic contract example containing only replay identities, hashes, provenance, split labels, and derived metrics. Authenticated replay payloads and credentials remain local-only.

## Research and provenance boundary

- Kaggle's public Adaptive Farming Strategy v6 was consulted as the public Adaptive Replay/live-agent reference. Its published Apache-2.0 notebook boundary is recorded by URL/version/hash; no replay payload was copied.
- Kaggle's official `kaggle-environments` Kaggriculture contract at commit `28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c` documents public observations, two-player runtime, local closed-loop execution, episode listing, and replay download. The acquired contract SHA-256 is pinned in the manifest.
- A replay source must declare `identity_only=true` and `raw_boundary=local-only-not-committed`. The validator rejects raw replay/action payload keys, credentials, malformed hashes, or unresolved sources.

## Pre-registered adaptive split

The split plan is frozen before evaluation and isolates local, public, and live cohorts across opponent lineage, episode, seed, seat group, chronological time slice, and market regime. Every pairwise overlap is emitted and must be empty. Chronology must satisfy `local < public < live`; any axis collision fails closed.

The committed fixture is deliberately small and synthetic so the contract can be tested without publishing authenticated bytes. Production ingestion can derive the same fields locally, replace the fixture's records, and retain only identity hashes plus aggregate outcomes.

## Transfer trust

For each split the report emits closed-loop mean rank, margin, p20 lower tail, worst margin, and win probability. Public-vs-local and live-vs-local gaps are explicit. Transfer trust is the conservative complement of the worst normalized rank, margin/lower-tail/worst, or win-probability drift; it is a diagnostic score, not evidence that samples are IID.

Open-loop recorded-action traces are separately counted as stress evidence. Their margin is reported under `open_loop_stress`, and their win probability must be null. They are never pooled with closed-loop win probability.

## Reproduction

```bash
python3 scripts/measure_adaptive_replay_oracle.py
python3 -m unittest tests.test_adaptive_replay_oracle
sha256sum docs/measurements/SOT-2975/SOT-2975-adaptive-replay-oracle.json
python3 scripts/measure_adaptive_replay_oracle.py
sha256sum docs/measurements/SOT-2975/SOT-2975-adaptive-replay-oracle.json
```

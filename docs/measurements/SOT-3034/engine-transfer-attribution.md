# SOT-3034 engine-grounded transfer attribution

## Result

The engine identity and interaction contract **passes**, while the current-field attribution result is
**inconclusive**. Four official-engine C95 episodes (starter/random, same seed in both seats) completed
720 steps. The exact identity

`terminal market value = engine-base terminal inventory + shared-market impact`

had zero residual on every transition. Market/terminal co-firing occurred 2,436 times and the public-only
opponent-relative exposure interaction fired 2,354 times. These are real official-runtime trajectory
events, not replay-derived lookup evidence.

## Current-field association

The pinned chronological current-field cohort contains outcome/rank/margin metadata, but deliberately
contains no actions, private states, or replay bytes. Its C95 paired mean margin moves from `+1,333.3`
in screen (0/3 negative pairs) to `-700.0` in sealed confirm (3/3 negative pairs), a `-2,033.3` drift.
That association motivates the transfer gap but cannot causally assign it to a trajectory component.
The result therefore remains inconclusive rather than rejecting an unobservable interaction.

## Candidate-independent metrics

- Terminal identity: values own inventory at official engine base prices and isolates only the public
  shared-market deviation. The equality residual prevents double counting.
- Opponent exposure: change in own public money/crop/animal capital proxy minus the corresponding public
  opponent change. No opponent-private inventory or action is used.
- Firing: records whether terminal-base and market-impact changes co-occur, and whether market impact
  co-occurs with non-zero opponent-relative public-capital movement. Counts are also split by phase.

The metric implementation contains no C95-specific thresholds or action knowledge; C95 is only the
evaluated trajectory source.

## Difference from SOT-3017

SOT-3017 ranked additive planning-to-trajectory gap buckets against an official starter/random fallback.
This issue adds (1) an exact terminal/market cross-term residual, (2) public opponent-relative exposure
and phase-level co-firing evidence, and (3) an explicit join to the newer chronological current-field
screen/confirm association while preserving its metadata-only boundary.

## Provenance and safety

The JSON artifact pins SHA-256 for the official engine-derived snapshot, C95 source manifest, and
current-field manifest. Those manifests in turn pin source URL, version/commit, SHA-256, and license.
The official engine is `kaggle-environments==1.32.7`, commit
`28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c`, Apache-2.0. The public crop-pay notebook is design-only
because its license is unspecified; no code was copied. No external replay bytes, fixed actions,
credentials, policy change, candidate promotion, or Kaggle submission were used.

Regenerate with:

```bash
python3 scripts/measure_engine_transfer_attribution.py
```

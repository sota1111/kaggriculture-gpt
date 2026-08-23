# SOT-3035 current-field transfer-trust report

## Decision

The oracle contract passes its provenance and leakage checks, but the evaluated transfer result is
**rejected**. C95 is selected by the screen (mean rank `1.0`, paired mean margin `+1,333.3`) and then
falls to mean rank `2.0` and paired mean margin `-700.0` in the sealed chronological confirm. The
incumbent is best in confirm (mean rank `1.0`, paired mean margin `+700.0`). This is an oracle-trust
finding only: no agent is promoted and no Kaggle submission was made.

## Reproducible provenance boundary

The manifest pins URL, observed version, SHA-256, license, and a
`fetch-only-not-committed` boundary for the public *What the Top Farms Do — a Live Meta*, *Daily
Replays: The Live Meta Report*, and official runtime contract sources. It pins the exact local bytes
for the incumbent, C95, and the independently packaged CARE-production candidate. Only identity,
timestamp, lineage, seat-paired margin/rank metadata, and hashes are committed. Replay bytes,
credentials, private traces/state, and action traces are rejected by the validator.

The manifest SHA-256 is
`7ca64565b5dce64012adea0195744975d3476203a6e190b16882a98ad4dfd4a0`. Regeneration is:

```bash
python3 scripts/measure_current_field_transfer_oracle.py
```

## Chronological split and leakage result

The cohort builder sorts by immutable `observed_at` before applying the pre-registered split. Screen
contains the first three episodes and confirm the next three. Confirm is mechanically excluded from
selection and used only as a post-selection trust check. Opponent, lineage, episode, seed, and time
cohort intersections are all empty. Every target is compared at the same episode seed in both seats.

| Target | Screen rank / mean / p20 | Confirm rank / mean / p20 | Mean drift | Rank drift |
| --- | ---: | ---: | ---: | ---: |
| incumbent | 1.0 / +700 / +200 | 1.0 / +700 / +400 | 0 | 0.0 |
| C95 | 1.0 / +1,333 / +900 | 2.0 / -700 / -1,200 | -2,033 | +1.0 |
| CARE-production | 2.0 / -717 / -1,100 | 1.67 / -217 / -450 | +500 | -0.33 |

The JSON artifact also records worst-tail margin, W/D/L, and deterministic seat-pair bootstrap 95%
intervals for each target and window. These measures expose screen-to-confirm drift; they do not turn
public replay observations into a live win-probability estimate.

## Safety boundary

Public corpus material is used as an opponent/time distribution and metadata provenance source, never
as a fixed-action policy or replay lookup table. No raw replay or credential material is present in
the repository. The incumbent remains an independent hedge, the failed C95 transfer is not an agent
rejection, and this issue performed no Kaggle submission.

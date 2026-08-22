# SOT-3018 current-field sealed evaluator

## Frozen cohort and leak boundary

The cohort is frozen at `2026-08-22T11:45:00Z` with canonical SHA-256
`5824794572c62eaede96104f6e3b69eab408a656b45788324a7374b7e42b2df8`.
Only opponent identities, lineage identifiers, episode identities, seeds, seats, time slices, hashes,
and derived W/D/L and margin summaries are committed. Replay bytes, action payloads, private state, and
credentials are excluded.

Stage A, Stage B, and final holdout are disjoint across opponent, lineage, episode, seed, and time.
Every episode is paired across seats 0 and 1. The manifest hash makes any cohort mutation fail closed.
The final holdout contains identities only: no outcome or relative margin is present.

## Screen to confirm result

| Candidate | Stage A W/D/L | Stage A mean / p20 | Stage B W/D/L | Stage B mean / p20 | Mean drift |
| --- | ---: | ---: | ---: | ---: | ---: |
| C95 | 2/1/1 | +2,125 / -1,800 | 2/0/2 | +200 / -3,200 | -1,925 |
| incumbent | 2/1/1 | +2,175 / -900 | 2/1/1 | +1,000 / -2,100 | -1,175 |

The opponent-seed seat-pair bootstrap 95% intervals are saved in the JSON result. Stage B favors the
incumbent on mean relative margin, so the pre-final selection is `incumbent`. This is transfer-evaluation
evidence, not a C95 rejection or a submission decision; the final holdout remains reserved.

## Mechanical non-selection guarantee

`candidate_selection_inputs` is exactly `["stage_a", "stage_b"]`. The validator rejects a final row
containing outcomes and records `final_holdout.opened=false` and `used_for_selection=false`. Tests cover
immutability, all split dimensions, both-seat pairing, final leakage, bootstrap output, and the
`NOT_PERFORMED` submission contract. No Kaggle submission was made.

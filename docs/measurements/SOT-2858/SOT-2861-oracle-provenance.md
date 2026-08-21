# SOT-2861 layout / productive-completion oracle provenance

The committed fixture contains derived public-state snapshots only. Authenticated replay bytes,
credentials, hidden state, post-action observations, future prices/actions, and reward fields are not
committed or consumed.

Sources are pinned by repository URL, 40-character commit, and source-file SHA-256 in
`tests/fixtures/layout_completion_oracle.json`. The screen and confirm windows hold out opponent,
episode, seed, and time identities; confirm is strictly later. Both windows contain both seats, and
each top-agent snapshot is compared with the champion on the identical seed and seat label.

Metrics use only the current public snapshot:

- layout: Manhattan distance from each visible pasture/crop placement to the shed;
- crop and pasture placement counts;
- requested, completed, incomplete, and completion-rate counts for the layout, crop, livestock,
  and movement decision families.

`scripts/measure_layout_completion_oracle.py` fails closed if a private/future/replay field appears,
if a split identity overlaps, if either seat is absent, or if provenance is not pinned. The generated
report records fixture/policy hashes and a deterministic report hash. No Kaggle submission was made.

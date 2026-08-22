# Third-party attribution

`agent.py` is the independently packaged V102 output from prvsiyan's Kaggle
notebook “Kaggriculture Frontier | The Moon Counts Melons”, script version
`343793897`. Kaggle marks that version as Apache-2.0.

The exact upstream notebook, output `main.py`, output archive, and packaged
agent hashes are pinned in `source.json`. The only packaging edit removes a
redundant trailing entrypoint alias so this repository's `main.py:agent`
validator sees `agent` as the final callable. No policy logic was changed.

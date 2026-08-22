# Kaito v39 history-gate candidate

This is an independent, default-off whole-agent evaluation. It does not patch
`main.py`; the current champion remains the hedge.

The public Kaggle output has no declared redistribution license. Accordingly,
the candidate code and archive are fetched transiently, verified against the
hashes in `source.json`, evaluated, and discarded. Only provenance metadata and
derived measurements are committed. Runtime routing is audited against the
public observation boundary, including checkpoints 96/120/122/132/144,
distance guards, and conservative fallback for unfamiliar states.

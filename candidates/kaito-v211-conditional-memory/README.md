# Kaito v21.1 conditional-memory clean-room candidate

This candidate evaluates the public v21.1 idea as a default-off, independent
whole agent. It is deliberately separate from the v39 sparse-history gate:
v39 selects a calibrated continuation at fixed delayed-history checkpoints,
whereas this candidate learns only within the current episode and may reorder
SELL orders when a prior public opponent-state signature is close enough.

The Kaggle metadata declares no redistribution license. The published source,
compressed routes, prototype bytes, notebook, and archive are therefore not
committed. `adapter.py` is a clean-room implementation of the public condition:
it wraps the pinned MIT lonespear whole-agent foundation, records public
opponent-state signatures, and preserves the foundation action unchanged on a
memory miss, an out-of-support signature, or an invalid observation. It never
creates or changes the quantity of a SELL order.

Screen and confirm identities are pre-registered in the fixture. Confirm is
strictly later and disjoint across opponent, lineage, episode, seed, seat-group,
and time slice. The current champion remains unchanged as the production hedge.

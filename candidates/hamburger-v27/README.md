# Hamburger V27 clean-room baseline

This is an independent, default-off whole-agent reconstruction of the public
Hamburger V27 behavioural specification. The downloaded public snapshot is
identified in `source.json`. Its metadata did not declare a redistribution
license, so no upstream Python, compressed blobs, or replay/action data are
included.

The package combines a deterministic state-derived anchor, collision-aware
SELL ordering, and a step 716–718 terminal inventory relay. It uses only the
Python standard library and exposes `agent(obs, config=None)` for offline and
file-runner execution. It does not modify `main.py`, the committed C95
candidate, or `submission.tar.gz`.

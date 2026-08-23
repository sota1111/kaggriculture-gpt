# Adaptive Replay provenance boundary

This directory is a provenance-only, fail-closed descriptor for the public
`02 Adaptive Replay Agent` notebook. It intentionally contains no upstream
source, generated agent, compressed action blob, decoded schedule, or replay
bytes.

The authenticated snapshot showed that the entry point begins with the action
at the current index of a 719-step replay-derived table. The advertised live
adapters repair, reorder, or shift those scheduled actions; two adapters also
read earlier or next-step entries from the same table. There is therefore no
standalone adaptive policy to ablate after the fixed schedule is removed.

Kaggle's downloaded metadata and notebook body declared no redistribution
license. Verbatim reuse is prohibited. The generic observations (rank
market-impacting sells, react to weeds, liquidate near termination) are not a
portable whole-agent candidate and overlap mechanisms already evaluated in
this repository. The incumbent remains an independent hedge, the sealed panel
stays unopened, and no Kaggle submission was made.

Run `python3 scripts/audit_adaptive_replay_provenance.py` to validate the
committed boundary. Pass `--source-dir` only with a transient authenticated
pull to recheck its two acquisition hashes; the tool never copies those bytes.

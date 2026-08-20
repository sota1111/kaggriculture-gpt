# SOT-2845 sequence planner sealed gate

The candidate was evaluated against the preceding champion by same-seed direct A/B in both seats. The screen used two opponent archetypes; opponent, episode, seed, and time identities reserved for confirm were disjoint and later than screen identities.

The rank-first screen rejected the candidate. Across four matches, mean rank improvement and reward delta were both zero. Worst and lower-tail margin delta were -138, productive actions decreased by 521, and travel actions increased by 489. The planner fired 801 times with 801 multi-step firings and 1,225 repairs, so this is a live isolated intervention rather than a non-firing inconclusive result. Invalid actions, capacity violations, and contract violations were zero; runtime ratio was below 2.0.

Because screen failed, sealed confirm was not consumed. `RECEDING_HORIZON_SEQUENCE_PLANNER` is reverted to `false`. Submission validation and exec compatibility pass, and no Kaggle submission was performed. The JSON artifact records all per-match rows, immutable opponent hashes, the manifest hash, and separate screen/confirm identity evidence hashes.

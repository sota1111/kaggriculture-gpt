# SOT-2908 sealed promotion decision

The independently gated step-0 `BUY_PRODUCT WHEAT 5` market lead was evaluated
with flag-off/flag-on direct A/B runs at the same seed in both seats. The screen
and confirm cohorts are disjoint by public opponent entity, episode, seed, and
time index. Confirm was opened only after the screen cleared the strict
rank-or-mean-margin gate without lower-tail or worst-margin regression.

Decision: **promoted**. `PUBLIC_STEP0_WHEAT_MARKET_LEAD` is now default on.
The report explicitly records `cv_representative=false`; this local public panel
is a proxy and does not claim live-leaderboard representativeness.

The machine-readable JSON records rank, mean/lower-tail/worst margin,
productive completion, terminal cash, per-seat firing telemetry, runtime ratio,
effective-config fingerprint, source/artifact hashes, and archive/entrypoint
compatibility. No Kaggle submission was performed.

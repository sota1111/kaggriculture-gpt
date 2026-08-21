# SOT-2907 public step-0 WHEAT market lead

SOT-2906 identified `market` as the first real divergence in all four screen episodes: at step 0 the
champion emitted `BUY_SEED WHEAT 2`, while Rayk C95 emitted `BUY_PRODUCT WHEAT 5` and Boatlee V16-RC5
emitted `BUY_PRODUCT WHEAT 14`. SOT-2907 independently reimplements only the narrower five-WHEAT
decision behind `PUBLIC_STEP0_WHEAT_MARKET_LEAD = False`; it copies no source code or full route.

The pinned provenance is the Rayk public notebook URL, kernel 129396610, acquisition snapshot dated
2026-08-21, notebook SHA-256 `a7447511510ed22b73f2315246b6bf4de66f219ffe3ba692a377f3fb47931331`,
and extracted C95 SHA-256 `489f5d197527f107027626cce79d850fd2ca90edd43d94384b849b6511e27bdb`.
The downloaded notebook declares no license, so its source is not copied; only externally observed
action telemetry is independently expressed. The boundary is step/player, own public cash,
and public WHEAT price. Identity, seed, replay bytes, private/future state, routes, and weights are excluded.

`python3 scripts/measure_public_step0_wheat_market_lead.py` records targeted firing for both seats,
flag-off/non-trigger/non-market exact invariance, action-contract compatibility, and per-seat ablation
telemetry. The SOT-2908 confirm cohort remains unopened. No Kaggle submission was performed.

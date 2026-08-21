# SOT-2877 sealed tomato-scarcity decision

The re-anchored screen ran the Moon V56 and public-top opponents on seeds 287501/287502, with the
candidate in both seats and a same-seed champion/candidate direct A/B. A complete second execution
reproduced every non-timing metric. All four pairs had zero rank, margin, lower-tail, worst,
productive-completion, and terminal-cash delta.

The fork did not trigger in any screen run, so seed-relay, plant, harvest, and terminal-sale fire
counts were also zero. The result is therefore `inconclusive`, rather than `rejected`: the rejection
contract requires both direct A/B and fire evidence. The strict screen gate failed and the untouched
Soil V19 confirm cohort was not consumed.

The effective configuration remains `MOON_V56_TOMATO_SCARCITY_FORK=false` (fingerprint
`b3f374198834a19dc89d3c106f362ec907dcca947e6827c0636d852d475871b4`). The configured candidate hash
is `a689448d0d74f57abf8a52584c05258756cc9d7ef7a52a4d06fff54a72148f68`; the configured champion hash
is `c7336bf09b6da1e02a9bf19bad0136cd9da1d67d8e39766822c6871ff4b418e1`. Submission contract and exec
compatibility passed, `submission.tar.gz` was not regenerated, and no Kaggle submission was performed.

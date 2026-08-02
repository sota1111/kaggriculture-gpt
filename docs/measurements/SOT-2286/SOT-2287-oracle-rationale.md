# SOT-2287 evaluation-oracle re-anchor

The v1 oracle ranked candidates primarily by final assets. That allowed malformed or execution-invalid actions to look locally strong even though the submission environment can discard those turns. The v2 fixture records the observation clock, daily hire reset, next-turn worker availability, market order cap, worker cap, and simultaneous tile-operation rule. Worker and market action arity, crop names, positive integer quantities, and hand counts are now checked before simulation.

The leaderboard-divergence proxy is `final_assets - 1000 * invalid_actions`. A candidate whose offline assets improve while this proxy falls, or whose contract violations increase, is treated as an oracle-drift signal and rejected. Screen seeds `[11, 23, 47]` and independent confirm seeds `[101, 211, 307, 401, 503]` remain fixed and reproducible.

Against champion `tests/fixtures/champion_sot_2263.py`, the current candidate passed both gates with zero invalid actions and zero contract violations. Mean proxy/assets were 5060.33 vs 4356.67 on screen and 4968.80 vs 4352.00 on confirm. The candidate is therefore promoted, and `scripts/validate_submission.py` confirmed exec compatibility. No Kaggle submission was made.

Machine-readable evidence: `SOT-2287-oracle.json`.

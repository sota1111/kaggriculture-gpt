# SOT-2886 public-shop egg cohort screen

Moon V56 was fetched only for evaluation from its exact public Kaggle notebook (version 56). The
notebook SHA-256 is `97be5f16511523daec1de44bc533e385353cc4e7d2170e88a6a4f31a123c5b5f` and the extracted
agent SHA-256 is `d2f51ca8851e563e3b8d24aeda28ff358bfdb8901039a89c39ff2e75aac68179`. The downloaded notebook
declares no license in its metadata, so no source code was copied into the runtime agent.

The screen ran seeds 288601 and 288602 with the champion in both seats against Moon V56 under
`kaggle-environments==1.32.7`. Shop prefixes were read from each live public observation at the gate;
they were not derived from the seed. The evaluator reproduced V56's two-egg-shop gate and its
YARN_STORE, triple-BAKERY, ICE_CREAM+BAKERY, clone, and opponent-GOOSE vetoes using public farms only.
Private state, future outcomes, episode identity, and seed-as-policy-input are fail-closed.

All four episodes finished `DONE/DONE`. Neither seed exposed two BAKERY/BRUNCH_SPOT shops: observed
egg-shop counts were 1 and 0. Accordingly, both policies recorded 0 egg gate actions, 0 egg production
actions, 0 egg sale quantity, and no decision-family divergence. The reference gate fired 0 times and
the `fewer_than_two_egg_shops` veto was recorded in every policy/seat episode. Terminal reward margins
are retained per row in the JSON as revenue context, but they are not attributed to egg behavior when
the cohort never fired.

Result: **inconclusive**. No egg mechanism is ported. The disjoint confirm entity/episode/seed/time
cohort (`soil-v19-confirm`, seed 288611) remains `RESERVED_UNOPENED`, and no Kaggle submission was made.
The complete machine-readable evidence is in `SOT-2886-egg-cohort-public-screen.json`.

# SOT-2949 factorial private-proxy oracle

The screen and confirm designs are independently balanced 2^4 panels over market regime,
opponent lineage, seat, and chronological slice. The confirm identity digest was fixed before
screen execution and rechecked before its one-time opening. Opponent lineage, episode, seed,
and time slice do not overlap between windows. Within every market/opponent/time cell, both
seats are run at the same seed, providing direct paired seat evidence.

All 32 closed-loop episodes reached `DONE/DONE`. The champion's overall mean margin moved from
`-175099.5` on screen to `-2286208.0` on confirm, while p20 margin moved from `-212545.0` to
`-5644740.0`. The largest main-effect confirm-minus-screen margin drift is market
(`-4318043.75`), followed by time (`+1108743.0`), opponent (`-949300.25`), and seat
(`+106402.5`). Material pairwise interactions include opponent×time (`-1427609.25`) and
market×time (`+989338.75`). Rank effects are zero because the champion ranks second in every
factorial cell; this ceiling/floor behavior means rank alone is not a trustworthy transfer signal.

The measurement is therefore `inconclusive`: it diagnoses strong market/opponent/time transfer
drift but does not reject or promote a policy. The JSON report records every row, factor main
effect, pairwise interaction, absolute transfer-trust score, source URL/license/commit/hash,
panel hashes, engine pin, separation checks, and runtime statuses. No private/future input,
authenticated replay, or Kaggle submission was used.

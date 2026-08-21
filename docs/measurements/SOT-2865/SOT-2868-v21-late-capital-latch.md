# SOT-2868 V21 late-capital latch direct A/B

The independent `V21_ONE_TIME_LATE_CAPITAL_LATCH` is default-off. At the first observation on or after
step 577 it records one decision per seat from `step`, `player`, and both farms' public `money` only.
An own-bank lead of at least 5,000 latches abstention and filters only new capital orders produced by
the existing scheduler and cash constraints; no source route or action trace is copied.

The targeted intervention fired and suppressed capital orders in both seats, made exactly one decision,
passed the inclusive 4,999/5,000 threshold boundary, and was invariant to episode, submission, seed, and
private metadata changes. The same-seed/both-seat direct screen completed four pairs with zero rank,
reward, tail, productive-completion, harvested, or terminal-cash delta and no invalid actions or contract
violations. Because the primary KPI did not improve, the screen rejected the axis, confirm was not
consumed, and the production flag remains false. No Kaggle submission was performed.

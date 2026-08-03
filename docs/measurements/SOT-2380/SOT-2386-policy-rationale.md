# SOT-2386 regime-aware policy portfolio

## Hypothesis and information boundary

The evaluated selector deterministically classified each public observation by:

- cultivable-board openness (open / unlocked tiles),
- remaining season horizon,
- volatility of the published current/forecast crop prices, and
- cash and seed inventory pressure relative to active workers.

It selected a small, weight-free portfolio: the current best-return/price-aware
policy, an immediate-liquidation variant for short/pressured regimes, and a
wheat-focused stability variant for open volatile regimes. No private simulator
state, confirm seed, randomness, learned weight, or Kaggle feedback was used.

## Fixed screen decision

Thresholds and regime rules were fixed before the independent confirm set. The
screen matched the champion exactly: mean reward `4366.75`, lower-tail `4123`,
and worst-case `4123`, with zero invalid actions and contract violations. Because
there was no strict lower-tail or worst-case improvement, the candidate failed the
promotion gate and confirm was skipped. The selector implementation and its agent
tests were reverted; the champion remains unchanged.

The evaluator now explicitly requires a strict lower-tail or worst-case gain for
this class of promotion, preventing an equal-score portfolio from being promoted.
The complete machine-readable evidence is in
`SOT-2386-regime-policy-portfolio.json`. No Kaggle submission was made.

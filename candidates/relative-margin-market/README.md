# Relative-margin market policy

This default-off candidate wraps the retained champion's field executor with an
independent, public-state market planner.  It estimates rival production from
the visible farm footprint, combines that with current town demand and shared
inventory/price, and scores a finite set of joint production/market plans by
`own_profit - opponent_denial_cost` (equivalently, expected relative-margin
change).

The candidate never reads `private`, future observations, replay identity, or
seed.  It preserves the ten-order contract and a public cash runway.  It is an
evaluation artifact only: `main.py` and `submission.tar.gz` remain the champion
unless both the screen and sealed confirm gates pass.

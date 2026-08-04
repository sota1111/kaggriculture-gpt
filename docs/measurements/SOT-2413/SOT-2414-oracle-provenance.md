# SOT-2414 competitive-oracle provenance

## Public contract evidence

- Kaggle's public `kaggle-environments` repository documents episode evaluation and the
  shared environment/agent lifecycle: <https://github.com/Kaggle/kaggle-environments>.
- The installed public `kaggle_environments` 1.28.0 package's Kaggriculture README and
  schema were inspected. The pinned evidence hashes were `6b9db7c...945cb5c` (README)
  and `dcd33a8...847a44` (interpreter). They specify two public farms, player-private
  shed/seeds/worker inventories, one shared dynamic market, unit-by-unit concurrent
  orders, market-before-refresh processing, and terminal bank money as reward.
- Kaggle competition, Code, and Discussion searches on 2026-08-04 found no indexed
  Kaggriculture-specific public top solution. Meta Kaggle Code is the portable public
  notebook corpus, but no competition-specific method was discoverable from its public
  index: <https://www.kaggle.com/datasets/kaggle/meta-kaggle-code>.

## Portable implementation

`run_competitive_market` replays multiple farms against one shared market. Orders at
the same queue position receive the same pre-commit quote, then commit one unit per
player before the next unit is priced. Seeds are private to a player but shared across
that player's farmer/hands; carried inventories remain per worker. It emits terminal
cash scores, deterministic ranks, player-0 relative score, winner, shared-market state,
and a unit-level quote/commit trace.

The fixed screen (`seed=2414`) passed with scores `[3063, 3025]`, ranks `[1, 2]`, and
relative score `38`. Only then did the independent confirm (`seed=9413`) run; it passed
with scores `[3053, 3049]`, ranks `[1, 2]`, and relative score `4`. Both gates and every
check are machine-readable in `SOT-2414-competitive-oracle.json`.

## Candidate decision

The unchanged policy candidate failed the existing distribution screen, so its
independent policy confirm was skipped and its decision remained `REJECT`. No candidate
policy code was promoted or retained. The competitive-oracle axis itself is promoted as
evaluation infrastructure because its fixed screen and independent confirm both pass.
Submission-contract validation remains successful, and no Kaggle submission was made.

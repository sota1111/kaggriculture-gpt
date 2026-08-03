# SOT-2339 runtime-oracle re-anchor

## Public evidence

The source of truth used for this re-anchor is the competition-owned file set downloaded with
`kaggle competitions download -c kaggriculture` on 2026-08-03 UTC:

- `README.md` (Kaggle creation timestamp `2026-07-28 18:52:49.709000`, SHA-256
  `c43a7ddfcd3fed022b5344e20dff6789f36799fbfe94d0bdd2ff71517f35e252`)
- `AGENTS.md` (same Kaggle creation timestamp, SHA-256
  `6dc2cc96a99a14eaace43e613121e327a14dc5a3cffbd3c424ff480f76f2d352`)

The files specify a 10×10 board with only the 5×5 NW quadrant initially unlocked, 24 turns/day for
30 days, market processing before farm updates, next-turn visibility of hires, harvest into per-unit
inventory followed by a shed drop at day end, two-unwatered-day crop death, and terminal **bank
balance** as reward. Unsold shed contents and seeds do not count.

## Drift found in oracle v2

| Contract | v2 behavior | v3 behavior |
| --- | --- | --- |
| Clock/board | 12×12 turns on an open 5×5 board | 30×24 turns on a locked-quadrant 10×10 board |
| Observation | Injected private evaluator hints (`crops`, `total_days`, `turns_per_day`) | Only public runtime observation keys |
| Harvest flow | Produce moved directly to shed | Produce enters the acting unit's inventory, then is shed-capped at day end |
| Crop survival/yield | Random yield at a simple maturity age | Public first-yield timing, watering bonus window, and two-day neglect-to-weed transition |
| Terminal objective | Cash + marked-to-market shed + seed value | Bank cash only |
| Action vocabulary | Crop-only subset rejected legal runtime actions | Full published worker/market vocabulary validates; unsupported domains are silent no-ops |

This is a material scale and semantics change, so v3 results are not numerically comparable with v2
measurements. The proxy remains deterministic and applies the existing hard invalid-action penalty to
the runtime reward.

## Screen → confirm decision

Machine-readable evidence is in `SOT-2339-runtime-oracle.json`. Fixed screen seeds `[11, 23, 47]`
passed before independent confirm seeds `[101, 211, 307, 401, 503]` ran. Both phases passed with zero
invalid actions and zero contract violations. Screen mean terminal reward was `4314.67`; confirm mean
was `4353.20`. The oracle axis is promoted, and `scripts/validate_submission.py` reports exec
compatibility PASS. No Kaggle submission was made.

The evaluator remains an intentionally bounded deterministic proxy: opponent interaction, dynamic
price curves, town demand, animals, fertilizer, structures, and land purchase effects are not yet
simulated. Legal actions in unsupported domains are no-ops rather than falsely modeled outcomes.

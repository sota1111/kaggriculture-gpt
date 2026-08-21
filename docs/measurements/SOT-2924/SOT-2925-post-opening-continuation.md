# SOT-2925 post-opening continuation re-anchor

## Result

The screen passed its leak-free and runtime gates. Starting at the predeclared market anchor step 161,
the first emitted divergence was `labor-routing` in all four episodes: Kaito v27 and 3094 moved `EAST`
while the champion emitted `HARVEST`. The result reproduced with the champion in both seats for each
seed. Production, labor-routing, inventory-feasibility, and market families all diverged later in every
episode. Two complete runs produced the identical JSON SHA-256
`d4e89a09b2143b93d6eca7d84eeafb4b0e9a00f7303dccbbb3f3bb30ff214327`.

## Port decision

No family is promoted from this screen. The first family, labor-routing, overlaps the ledger's rejected
static mixed-farm/route, adaptive route-repair, receding-horizon planner, and capacity-dispatch axes.
The observation that two current references both move east at step 161 is firing evidence, but it does
not isolate a new causal mechanism or justify retrying those CLOSED axes. The remaining family counts
are descriptive only and cannot support a coherent continuation port without an independent mechanism.

## Provenance and boundary

The JSON pins URL, Kaggle kernel id, acquisition version, notebook SHA-256, extracted executable hash,
and license status for Kaito v27 and 3094; Adaptive is hash-pinned as confirm provenance. Notebook and
agent bytes remain in ignored local storage and are not included in the submission or commit. The
policy comparison records public actions and terminal status/reward only. Private/future fields and
replay bytes are forbidden. Opponent, episode, seed, and time identities are disjoint between screen
and confirm. The Adaptive confirm cohort remains `RESERVED_UNOPENED` with null outcomes.

## Reproduction

```bash
python scripts/measure_post_opening_continuation.py \
  --source-dir .ai-jobs/sot2925-sources
```

Requires `kaggle-environments==1.32.4`. No Kaggle submission was performed.

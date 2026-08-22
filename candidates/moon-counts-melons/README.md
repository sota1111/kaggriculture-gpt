# Moon Counts Melons V102 independent whole agent

This directory vendors the Apache-2.0, standard-library-only V102 policy as a
default-OFF independent candidate. Production `main.py` neither imports nor
embeds it; the current champion remains an independent hedge.

Reproduce the preregistered same-seed/both-seat screen and the opponent,
episode, seed, seat, and time-disjoint confirm with:

```bash
.venv/bin/python scripts/measure_moon_counts_melons.py
```

The confirm manifest is hashed before the screen. Confirm is opened only if
rank or mean margin improves without p20 regression. The script never submits
to Kaggle.

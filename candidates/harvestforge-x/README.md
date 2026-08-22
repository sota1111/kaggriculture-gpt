# HarvestForge-X 3094 evaluation boundary

This directory deliberately does not contain the notebook, `main.py`, or its
archive. The public notebook does not declare a redistribution license, so the
candidate is evaluated fail-closed from a transient Kaggle API download whose
notebook, payload, and archive hashes are pinned in `source.json`.

The candidate remains independent and default-off. `main.py` (the champion) is
not modified, and no Kaggle submission is performed. Reproduction requires an
authenticated Kaggle CLI and runs `scripts/measure_harvestforge_x.py`; an exact
already-downloaded payload can instead be supplied with
`HARVESTFORGE_MAIN_PATH`.

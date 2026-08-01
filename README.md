# kaggriculture-gpt

GPT lineage for the Kaggle `kaggriculture` competition.

Build and validate:

```bash
bash scripts/build_submission.sh
```

Submit:

```bash
kaggle competitions submit -c kaggriculture \
  -f submission.tar.gz -m "kaggriculture-gpt champion"
```

The archive contains `main.py` at its root and exports `agent(obs)`.

The champion routes the farmer and daily farm hands to distinct prioritized
tiles (harvest, water, dig, then plant). It reserves cash before buying seeds or
hiring, caps market orders, and reserves each available seed for at most one
worker action. `HIRE_TARGET` is selected by the offline screen/confirm gate.

## Reproducible offline evaluation

Run a candidate through the fixed-seed screen and confirm gates:

```bash
python3 scripts/evaluate.py \
  --champion tests/fixtures/champion_sot_2262.py --candidate main.py \
  --output docs/measurements/SOT-2258/result.json
```

The JSON result records each screened HIRE count, the selected count, and
per-episode/mean final assets, profit, cultivated, harvested, and invalid
actions. The simulator uses a 5x5 field, movement, weeds, daily hand resets,
seed accounting, and Fibonacci hire costs. Thresholds and seed sets live in
`tests/fixtures/evaluation.json`. Confirm is skipped unless screen passes. A
rejected candidate must be reverted while retaining the result JSON. Promotion
automatically runs the submission contract check and only emits
`next_action: kaggle_validation` after it passes. Build the exact archive with
`bash scripts/build_submission.sh` before the Kaggle validation run.

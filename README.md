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
tiles (harvest, water, dig, then plant). It scores known crops by expected daily
margin using seed price, maturity, yield, and the current market price. Inventory
is held below its configured sell target and sold into stronger markets. Cash is
reserved before seed purchases or hiring, market orders are capped, and each
available seed is reserved for at most one worker action.

## Reproducible offline evaluation

Run a candidate through the fixed-seed screen and confirm gates:

```bash
python3 scripts/evaluate.py \
  --champion tests/fixtures/champion_sot_2263.py --candidate main.py \
  --output docs/measurements/SOT-2258/SOT-2264-crop-market.json
```

The JSON result records each screened crop/sale strategy, the selected strategy, and
per-episode/mean final assets, profit, cultivated, harvested, and invalid
actions. The simulator uses a 5x5 field, multiple crops, changing daily prices,
movement, weeds, daily hand resets, seed accounting, and Fibonacci hire costs. Thresholds and seed sets live in
`tests/fixtures/evaluation.json`. Confirm is skipped unless screen passes. A
rejected candidate must be reverted while retaining the result JSON. Promotion
automatically runs the submission contract check and only emits
`next_action: kaggle_validation` after it passes. Build the exact archive with
`bash scripts/build_submission.sh` before the Kaggle validation run.

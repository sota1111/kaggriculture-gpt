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

## Reproducible offline evaluation

Run a candidate through the fixed-seed screen and confirm gates:

```bash
python3 scripts/evaluate.py \
  --champion main.py --candidate path/to/candidate.py \
  --output docs/measurements/SOT-2258/result.json
```

The JSON result records per-episode and mean final assets, profit, cultivated and
harvested counts, and invalid actions. Thresholds and seed sets live in
`tests/fixtures/evaluation.json`. Confirm is skipped unless screen passes. A
rejected candidate must be reverted while retaining the result JSON. Promotion
automatically runs the submission contract check and only emits
`next_action: kaggle_validation` after it passes. Build the exact archive with
`bash scripts/build_submission.sh` before the Kaggle validation run.

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

The independent `SHED_OVERFLOW_PROTECTION` component coordinates carried
inventory, the public shed capacity, and the nightly clock. It drops goods when
room exists and sells only the minimum low-value shed stock needed to prevent
the next refresh from discarding carried harvest. It does not enable projected
market execution or terminal recovery. Reproduce its same-seed/both-seat
screen and independent confirm with:

```bash
python3 scripts/measure_shed_overflow.py \
  --output docs/measurements/SOT-2795/SOT-2798-shed-overflow.json
```

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

## Authenticated replay anchor

The current-top replay corpus is pinned by submission, episode, opponent entity,
seat, seed, timestamp, raw replay SHA-256, and deterministic archive SHA-256 in
`tests/fixtures/authenticated_replay_manifest.json`. Verify the committed evidence
offline or re-fetch it through the authenticated Kaggle API:

```bash
python3 scripts/fetch_authenticated_replays.py --offline
python3 scripts/fetch_authenticated_replays.py
python3 scripts/measure_authenticated_replay_cv.py
```

The raw archives are audit artifacts, not candidate features. The evaluator only
projects identity and chronological public metadata; private observations and
future steps are excluded. The older public-source corpus remains an explicitly
separate fallback and is never presented as authenticated live-ladder evidence.

## Adaptive route-repair ablation

`scripts/measure_adaptive_route_repair.py` evaluates a public-state-only route
expert classifier and bounded suffix repair against the authenticated replay
manifest's seeds in both runtime seats. The mechanism is distilled from
`Seyamalam/Kaggriculture@8b8c421eb10634c756583ce10c75189f50c83a72`
(`agents/candidate_v8_market_order.py`, MIT, SHA-256
`10ce90c25f040e0286b340b212a595117435a609744bd0ad02f2ee0a51c420d4`).
Embedded action traces, fitted prototypes/weights, replay identities,
credentials, and private replay data are excluded. Run:

```bash
python3 scripts/measure_adaptive_route_repair.py \
  --output docs/measurements/SOT-2781/SOT-2783-adaptive-route-repair.json
```

The candidate is kept in the measurement harness only unless both screen and
independent confirm meet the strict rank/margin/tail promotion gate.

## Fertilizer coverage ablation

`scripts/measure_fertilizer_coverage.py` first compares recurring strawberry
fertilizer demand with available stock and emitted `FERTILIZE` actions. It only
tests bounded buying when supply is short; an action-bound trace instead tests
the independent assignment/coverage candidate. Run the same-seed, both-seat
screen and independent confirm with:

```bash
python3 scripts/measure_fertilizer_coverage.py \
  --output docs/measurements/SOT-2781/SOT-2784-fertilizer-coverage.json
```

The report records coverage, `FERTILIZE`/`COLLECT_FERTILIZER`/stock/buy counts,
rank and reward tails, runtime ratio, contract validity, and confirms that no
Kaggle submission was performed.

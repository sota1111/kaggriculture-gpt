# kaggriculture-gpt

GPT lineage for the Kaggle `kaggriculture` competition.

Build and validate:

```bash
bash scripts/build_submission.sh
```

The public COK-ZhangZiliang V7 whole agent is tracked separately as a
hash-pinned, fetch-only hedge descriptor under `candidates/v7-portable/`.
Its stdlib-only contract and local screen pass, but it is not vendored or
promoted: upstream's Apache notice licenses attributed route portions only,
not the independently written whole-agent controller. See
`docs/measurements/SOT-2934/SOT-2939-v7-portable-hedge.json`.

The V16-RC5 8C/4S premium-market direction is also packaged independently
under `candidates/v16-rc5-portable/`. The downloaded public notebook declares
no license, so its executable route is fetch-only; the committed candidate is
a clean-room, default-OFF implementation of only the published herd milestones
and inventory-feasible premium sale ordering. Its screen evidence is recorded
at `docs/measurements/SOT-2942/SOT-2944-v16-rc5-portable.json`; confirm remains
reserved for the common SOT-2947 portfolio gate.

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

The independent `MOON_V56_TOMATO_SCARCITY_FORK` is default OFF. It ports only
Moon V56's bounded tomato-scarcity boundary: two of the first three public
shops must be `PIZZA_SHOP`/`FARMERS_MARKET`, three strawberry seed/plant slots
are redirected to tomato, a market-full seed order may relay for eight slots,
and the cohort is tracked through 3 plants, up to 12 harvest actions, and a
terminal sale. The source is Kaggle notebook V56 at
`prvsiyan/kaggriculture-frontier-the-moon-counts-melons` (notebook SHA-256
`97be5f16511523daec1de44bc533e385353cc4e7d2170e88a6a4f31a123c5b5f`,
agent SHA-256 `d2f51ca8851e563e3b8d24aeda28ff358bfdb8901039a89c39ff2e75aac68179`).
No license declaration was present in the downloaded notebook metadata. The
portable patch excludes the source's full fixed route, replay identity, seed,
future outcome, opponent-private data, external weights, and submission logic.

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

### Private-proxy closed-loop oracle

The SOT-2938 oracle runs the champion in fresh closed-loop engine episodes against
four hash-pinned public opponent lineages. Screen and confirm are disjoint by
opponent lineage, episode, seed, and chronological slice; every identity is run
in both seats. It reports margin, rank, pessimistic tail, per-distribution
aggregates, and confirm-minus-screen transfer stability. Open-loop replay remains
a separately labelled diagnostic and is not included in transfer-trust:

```bash
python3 scripts/measure_private_proxy_oracle.py
```

The committed measurement pins the candidate, opponents, engine, manifest, and
seed-panel hashes. It performs no Kaggle submission.

The SOT-2943 extension additionally fixes four sparse official `marketParams`
regimes and holds market regime, opponent lineage, episode, seed, seat pair, and
chronological slice apart between screen and confirm. The repeatable
`--candidate NAME=PATH` option evaluates the champion and independently packaged
agents under the identical manifest. Confirm starts as `RESERVED_UNOPENED` and
its digest is checked after screen before any confirm episode is run:

```bash
python3 scripts/measure_market_shift_oracle.py \
  --candidate champion=main.py \
  --candidate hedge=candidates/example.py
```

The report uses one schema for margin, mean rank, p20/worst tail, per-market
regime summaries, and screen-to-confirm drift. Source URL, license, commit,
artifact hash, candidate hash, engine, manifest, panels, and market-regime hash
are recorded; private/future fields fail validation. The default command measures
the champion only and performs no Kaggle submission.

The SOT-2947 portfolio freezes that oracle and the V16-RC5, Strict-Future, and
diversified-scheduler candidates before opening any result. It evaluates every
direction on the registered screen and opens sealed confirm only for candidates
with rank-or-mean-margin uplift and a non-regressing pessimistic tail. Rejection
requires a same-identity A/B confirm regression plus real-firing evidence;
otherwise the result remains inconclusive. The old champion is retained unless
exactly one candidate clears both windows:

```bash
python3 scripts/measure_sealed_private_proxy_portfolio.py
```

The SOT-2941 portfolio freezes that oracle plus the independent V7 hedge and
fertilizer architecture artifacts before evaluating them. It consumes the
pre-registered confirm identities only after a candidate passes screen, uses
leak-free CV margin/rank/tails as primary evidence, treats public score as
refutation-only, and retains the prior champion unless the full gate passes:

```bash
python3 scripts/measure_independent_portfolio.py
```

The V7 source remains fetch-only and cannot be promoted while its whole-agent
redistribution license gate is unresolved. The portfolio never submits to
Kaggle.

The public-state productive-action capacity oracle measures executable work,
standing-on-work, mandatory travel, route-repair assignments, capacity
shortfall/utilization, and productive density without private or future fields.
Its entity/seed/time-separated screen and confirm panels cover both seats:

```bash
python3 scripts/measure_public_action_capacity_oracle.py
```

The JSON output pins the default-off champion and source/fixture/policy
provenance. This measurement does not submit to Kaggle.

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

### Winner-only teacher dataset

`scripts/build_replay_teacher_dataset.py` materializes a local JSONL teacher
dataset from the current top-ladder identities pinned in
`tests/fixtures/replay_teacher_manifest.json`. Each row contains the winning
seat's same-step public observation and next action. Winner team, episode, seed,
and time are isolated between screen and confirm; private/future/credential
fields fail closed. Replay bytes and the generated dataset stay local, while the
committed measurement records their deterministic hashes and coverage:

```bash
python3 scripts/build_replay_teacher_dataset.py \
  --dataset-output /tmp/kaggriculture-winner-teacher.jsonl
```

If authenticated acquisition is unavailable, do not describe fallback public
artifacts as current-top data; retain their hash/license-pinned fallback label.

### Decision-family divergence anchor

The SOT-2832 measurement compares the winner teacher's first emitted action in
each farmer/hand/market channel with the current champion's public-state
projection. It records frequency, divergence, reward-attribution proxy, and
fireability separately for screen and confirm, while excluding the CLOSED
land/labor compact-policy families from selection:

```bash
python3 scripts/measure_decision_family_divergence.py \
  --dataset .ai-jobs/sot-2832-teacher.jsonl \
  --replay-dir .ai-jobs/sot-2832-replays
```

The screen selected the economic family and the untouched confirm panel agreed.
The committed artifact contains only aggregate evidence and hashes; replay
bytes, the 4,320-row teacher dataset, credentials, and external weights remain
local. This measurement does not change `main.py` or submit to Kaggle.

## Adaptive route-repair ablation

`FEED_ECONOMIC_DECISION` is an independent, default-off ablation distilled
from zansued/kaggriculture-ai-agent@9de2779. It computes a bounded feed-wheat
runway from the current herd, wheat inventory, cash runway, remaining days,
and public shop demand. The SOT-2833 direct screen produced no live firings or
strict improvement, so the candidate remains disabled and confirm was not
consumed; targeted both-seat intervention evidence is retained.

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

The follow-up sealed decision gate is reproducible with:

```bash
python3 scripts/measure_feed_economic_sealed_panel.py
```

It uses opponent-, episode-, seed-, and time-disjoint screen/confirm identities,
compares the flag off/on with the same seed in both seats, and opens confirm only
after screen clears the rank/reward/margin noise and tail/contract gates. A
rejection leaves `FEED_ECONOMIC_DECISION = False` and performs no Kaggle submit.

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

The independent `FERTILIZER_CONSTRAINED_PRODUCTION` candidate is default OFF.
It works backward from the remaining worker-action budget and admits acreage
only when plant, fertilize, water, and harvest can all complete within observed
fertilizer supply, cash runway/next-hire cost, shed headroom, and terminal sale
capacity. It has no fixed quadrant, acreage, hand count, or route. Reproduce the
same-seed, both-seat architecture screen and bottleneck ablations with:

```bash
python3 scripts/measure_fertilizer_constrained_production.py
```

The committed report records the firing plan, productive completion, coverage,
margin/tail, effective configuration, and `NOT_PERFORMED` Kaggle submission.

## Licensed whole-agent hedge

The exact MIT-licensed `deepeshumrao/kaggriculture-agent` submission is retained
separately under `candidates/deepeshumrao-whole-agent/`. It is default OFF and
does not modify or wrap the champion. Its source commit, byte hashes, license,
and attribution are pinned alongside the artifact. Reproduce its current-public
both-seat screen and disjoint confirm with:

```bash
python3 scripts/measure_deepeshumrao_whole_agent.py
```

The result is deliberately `inconclusive`: the candidate follows a clearly
different action-family distribution, passes the runtime contract, but lost
all registered screen and confirm episodes. It remains a measured hedge only;
no public score was used and no Kaggle submission was performed.

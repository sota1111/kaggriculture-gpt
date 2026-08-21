# SOT-2906 current-public divergence screen

## Result

The first emitted action divergence was the `market` family in all four screen episodes. At step 0,
the champion emitted `BUY_SEED WHEAT 2`; Rayk C95 emitted `BUY_PRODUCT WHEAT 5`, and Boatlee V16-RC5
emitted `BUY_PRODUCT WHEAT 14`. The result held with the champion in both seats on each seed.

All later families also diverged at least once: labor and livestock at step 0, crop/route/task at step
1, and land at step 160. Therefore no family is reported as unfired. This screen attributes the first
observable difference; it does not claim that the market action causes higher reward.

## Provenance and information boundary

The machine-readable measurement pins the Kaggle URL, kernel id, acquisition version, notebook SHA-256,
extracted agent SHA-256 where executable, and license status for Rayk Findings, Boatlee V16-RC5,
3094-score, Adaptive Farming Strategy, and the official getting-started baseline. Only Rayk C95 and
Boatlee V16-RC5 were opened for this screen. The 3094-score and Adaptive cohorts are reserved as confirm.

Committed telemetry contains only step, seat, public action, terminal status, and reward. Private/future
state, episode identity as a policy input, replay bytes, credentials, and external weights are excluded.
No Kaggle submission was performed.

## Reproduction

```bash
python3 scripts/measure_current_public_divergence.py --acquire \
  --source-dir .ai-jobs/sot2906-sources \
  --output docs/measurements/SOT-2905/SOT-2906-current-public-divergence.json
```

The run requires `kaggle-environments==1.32.4`. Two complete reruns produced identical SHA-256
`a3892562afc3fc941cdc3b76fb757cdf3855647d27abccdb3709ea82d832d975`.

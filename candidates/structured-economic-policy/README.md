# Structured Economic Policy clean-room candidate

The referenced Kaggle notebook does not declare a redistribution license in
its downloaded metadata. Its code and archive are therefore not committed.
`source.json` pins the acquired notebook hash and archive fingerprints, while
`adapter.py` independently implements the economic invariants described in
the notebook's public prose: field-before-market budgeting, demand-responsive
production, workload-bounded labor, sale-before-purchase financing, and
terminal feasibility.

The adapter is combined offline with the exact MIT-licensed lonespear
foundation to create one standard-library-only `main.py`. It is default-OFF;
the repository champion and `submission.tar.gz` are not changed.

Reproduce the screen and sealed confirm with:

```bash
python scripts/measure_structured_economic_policy.py
```

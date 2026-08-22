# V16-RC5-R5A recovery candidate

This default-off independent candidate clean-room implements only the R5A-specific
livestock alignment recovery described by the pinned public notebook. The notebook
declares no license, so neither its executable nor replay-derived schedule is stored.
The implementation is layered on the separately attributed MIT lonespear whole-agent
foundation and has no dependency on `main.py`.

R5A differs from the previously evaluated V16-RC5 portable direction by adding a
bounded state machine: a cow-carrying actor blocked on its planned placement moves to
an adjacent empty pasture, places on the next turn, and resumes the foundation route.
Evidence and immutable fingerprints are produced by:

```bash
python3 scripts/measure_v16_rc5_r5a_recovery.py
```

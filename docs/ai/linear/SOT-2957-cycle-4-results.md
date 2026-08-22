# SOT-2957 cycle 4 aggregation

## Decision

The coherent lonespear CARE-production whole agent is selected as the cycle-4
submission candidate. It is kept structurally independent from the retained
production champion.

## Evidence

- SOT-2958 Barnyard Economist: screen/confirm margin delta +87,198 / +110,534.25;
  rank remained 2, retained as an independent hedge.
- SOT-2959 coherent CARE: screen and confirm both 4/4 wins; mean rank 2 to 1;
  margin delta +137,531.5 / +146,769.25; tail delta +130,175 / +141,241.
- SOT-2960 oracle: confirm-minus-screen mean/tail drift -2,007,925 / -4,088,390.
- SOT-2961 relative-margin policy: mean margin delta -11.75; confirm remained sealed;
  inconclusive and not selected.

## Effective configuration

- Source commit: `774b26093ccf4246525517d48420349b841b6e50`
- Agent SHA-256: `eb5b5f59a8ec2d40b77cc99d4ffe3b932136fdcf9f6b6e168726b7f07ab47cb0`
- Archive SHA-256: `0c188c379e23291bee39ff95b0aa6da3b14c737d2dc84866d0ebc13c61ea7787`
- Archive layout: one root `main.py`
- Runtime: stdlib-compatible; NumPy/SciPy optional with fallback; no weights,
  credentials, replay bytes, or network dependency.

The previous `main.py` remains unchanged as a hedge. Public LB is used only as
a contradiction signal and never as the selection metric.

## Submission decision

No submission was executed in this run. Kaggle ref `55678801` was submitted at
`2026-08-21T23:41:45.490Z`, and the required 180-minute spacing interval had not
elapsed at the final decision. The verified archive is retained for a later
governed slot; this operational skip does not reject the candidate.

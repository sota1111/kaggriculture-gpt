# SOT-2341 Robust Adaptive Policy

## Re-anchored failure mode

The distribution-shift gate exposed a fixed-capacity assumption: the champion always targeted four hired hands regardless of observed cultivable area. This under-provisioned the 6×6 unlocked confirm board, while blindly increasing the constant caused extra movement conflicts. The small-board screen already saturated the existing capacity, so a global worker-count increase was not robust.

## Single-axis hypothesis

Derive a bounded hand target from observed unlocked land and remaining realizable harvests, and make collision avoidance the first assignment constraint. A 4×4 unlocked area retains the champion target; a 6×6 area can add one hand; no hands are hired when no harvest remains. This adapts to board capacity, season horizon, and current worker count without relying on scenario names or hidden evaluator data.

## Screen → confirm result

- Screen: PASS. Candidate and champion lower-quantile/worst reward were both 4123; invalid actions and contract violations remained zero.
- Independent confirm: PASS. Lower-quantile reward improved from 4265 to 4368; mean reward improved from 4401.67 to 4438.83; mean assignment conflicts fell from 0.33 to 0.17.
- Exec compatibility: PASS.
- Decision: promoted. `main.py`, lineage, and the submission artifact are retained and updated.
- Kaggle submission: not performed; submission selection remains with parent SOT-2338.

The complete per-episode, lower-quantile, worst-case, and gate output is in `SOT-2341-adaptive-worker-capacity.json`.

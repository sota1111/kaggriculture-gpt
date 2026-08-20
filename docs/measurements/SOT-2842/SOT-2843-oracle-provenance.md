# SOT-2843 leak-free multi-step oracle provenance

- Policy under measurement: repository `main.py`, pinned by SHA-256 in the JSON artifact.
- Split: screen and confirm are disjoint by opponent, episode, seed, and time; confirm times are strictly later.
- Seat control: every panel contains seat 0 and seat 1 evidence.
- Transition scope: task, worker location, and player-owned seed/shed inventory are compared across at least three current-state observations per episode.
- Capacity scope: labor, travel, cash, seed, shed, and total action capacity are recorded at every step and fail closed on overuse.
- Leakage boundary: winner traces are not loaded or passed to the policy. Only immutable provenance SHA-256 values are retained. Any embedded private/future/winner-action field fails split validation before screen execution, and confirm is skipped.
- Gate order: isolated screen first; confirm is evaluated only after screen passes.
- Submission: `NOT_PERFORMED`. This issue does not invoke Kaggle submission tooling.

# SOT-2860 shed-centric layout-aware production

The independent `LAYOUT_AWARE_PRODUCTION_ARCHITECTURE` flag remains default
OFF.  When explicitly enabled, the upstream component admits crop planting
demand only when the current workers can complete planting and minimum service
within the public remaining horizon.  Empty placement candidates receive a
deterministic Manhattan-distance cost from the public shed position.  A first
pasture is generated only when public livestock specifications expose demand,
and uses the nearest shed-side empty tile.

The targeted intervention fired for both seats, capped infeasible crop demand,
emitted `BUILD_PASTURE`, and was deterministic.  Same-seed/both-seat screen and
opponent/seed/time-held confirm each improved mean, lower-tail, and worst reward
by 26 with no invalid-action or contract regression.  The confirm panel was
opened only after the screen passed.  See
`SOT-2860-layout-aware-production.json` for raw paired metrics.

The component reads the current public board, worker positions, shed position,
livestock specifications, and clock only.  It does not consume replay identity,
future state, opponent-private state, fixed traces, or external weights.  The
default-OFF path remains the champion path for the downstream sealed panel.
No Kaggle submission was performed.

# Final Report — SOT-2825

## Decision

REJECTED. The compact policy remains disabled (`COMPACT_REPLAY_POLICY=false`).

## Evidence

The untouched sealed panel ran four same-seed/both-seat real Kaggriculture matches. All reached 720 states and DONE/DONE with no stderr, invalid actions, or contract violations. Candidate mean rank stayed 2.0; margin deltas were +6299 mean and +912 lower-tail/worst, but own reward delta was -1194 in every match. Runtime ratio was 1.083 and the submission contract passed. A second run reproduced all non-timing output exactly.

## Acceptance

All SOT-2825 criteria are satisfied. The evidence-backed reward regression justifies rejection; independent confirm was skipped according to the screen→confirm contract, and no Kaggle submission was performed.

## Linear Report: POSTED

## Acceptance: PASS

# Final Report — SOT-3032

Adaptive Replay Agentはlicense未宣言で、実行の根幹がreplay-derived 719-step固定scheduleであることをhash-pinned evidenceとして記録した。verbatim/executable artifactをfetch-onlyとし、固定scheduleを除いて独立実行可能なclean-room候補は成立しないと判定した。incumbentとsubmission archiveは不変で、Kaggle提出は行っていない。

Verification: provenance/hash validator PASS、compileall PASS、278 unittest PASS（2 optional skips）、submission contract PASS、diff review PASS。

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW
# SOT-3034 Final Report

Engine-grounded market/terminal/opponent transfer attribution is implemented and verified. The exact
terminal market-value identity had zero residual, both requested interaction families fired in four
complete official-engine same-seed/both-seat episodes, provenance is pinned, and the delta from SOT-3017
is explicit. The current-field result is intentionally inconclusive because the safe cohort lacks
trajectory bytes; no rejection was inferred and no Kaggle submission occurred.

Verification: 285 tests passed (2 skipped), compileall passed, and diff check passed. npm gates are N/A
because this Python repository has no package.json or browser surface.

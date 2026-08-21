# SOT-2881 opening feed-priority sealed decision

The fresh current-public screen from SOT-2879 completed four episodes against Rayk C95 and Boatlee
V16-RC5, using the same seed in both seats for each opponent. All episodes reached `DONE`. The
opponents bought 5 or 14 WHEAT in market slot zero, but the champion emitted no step-0 WHEAT order,
bought no opening WHEAT, and therefore could not experience the feed-denial intervention.

SOT-2880's explicit prerequisite gate consequently left the runtime unchanged: there is no opening
feed-priority candidate or flag to compare with the champion. Fabricating a candidate A/B would break
the issue's evidence discipline. Rank, margin tails, productive completion, runtime, invalid-action,
and contract deltas are therefore recorded as not applicable rather than falsely reported as zero.

The result is `inconclusive`, not `rejected` or `CLOSED`, because required intervention firing is
absent. The untouched confirm cohort (`salemali7-3094` seed 287911 and `tetsutani-adaptive` seed
287912) remains `RESERVED_UNOPENED`. The effective state is
`OPENING_FEED_PURCHASE_PRIORITY=ABSENT`, fingerprint
`3c042347664bce3c43e39f6a37a75958cd2598d2fe3ad78a252bfe108453659d`.

The parent should not promote or submit this axis. `main.py` and `submission.tar.gz` are unchanged,
and no Kaggle submission was performed.

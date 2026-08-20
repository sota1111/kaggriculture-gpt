# SOT-2837 sequence-conditioned precursor policy

The SOT-2836 early `BUILD_PASTURE` task boundary was distilled into the
independent `SEQUENCE_PRECURSOR_POLICY` flag.  The default remains `False`.
When enabled, a bounded state machine recognizes one existing pasture and no
visible animals, records the current public market inventory, selects an empty
public tile adjacent to the pasture, approaches it, and emits exactly one
`BUILD_PASTURE`.  It expires after eight steps.  Cash and worker bands from the
attribution panel are deliberately not fitted as a one-shot threshold.

The targeted isolated ablation fired for both seats, reached the economic
action, and was invariant to injected episode/submission/seed metadata.  The
same-seed/both-seat closed-loop screen completed four paired matches (720
states, `DONE/DONE`, zero invalid actions and contract violations), but the
eligible public boundary never occurred.  Candidate and champion were therefore
identical: mean, lower-tail, and worst margin deltas were all zero.  The strict
improvement and live-firing screen gate failed, so untouched confirm was not
consumed.

The axis is rejected using the firing-bearing isolated ablation plus the direct
paired A/B.  Production retains `SEQUENCE_PRECURSOR_POLICY = False`; rejected
`FEED_ECONOMIC_DECISION`, mixed-farm, adaptive route repair, compact land/labor,
and productive-capacity axes remain disabled.  Submission contract validation
passed, `main.py:agent` remains the final callable, and no Kaggle submission was
performed.

# Final Report — SOT-2974

Kaito v19 Replication-to-Control was reproduced as an exact Apache-2.0,
standard-library-only independent whole-agent candidate. Source version and
hashes are pinned, and the intervention is explicitly separated from v39's
sparse-history gate.

The candidate won 4/4 episodes in both the registered same-seed/both-seat
screen and the opponent/episode/seed/seat/time-disjoint confirm, improving
rank, mean margin, and pessimistic tail against the retained champion. It is
promoted only as a default-OFF hedge; `main.py` and `submission.tar.gz`
remain unchanged, private traces were not shipped, and no Kaggle submission
was performed.

## Acceptance: PASS
## Next Action: READY_FOR_REVIEW

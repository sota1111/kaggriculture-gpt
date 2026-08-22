# SOT-3005 strict-future live-field oracle

## Provenance and freeze boundary

The panel implements the public zero-to-top-meta multi-leader/both-seat/live-loss audit and the v27
freeze-cutoff discipline without committing credentials or replay bytes. The acquisition attempt was
frozen at `2026-08-22T09:30:00Z`. Authenticated current-field replay refresh was unavailable before that
cutoff, so the registered fallback uses immutable derived summaries only. The opponents, episode digests,
foundation artifacts, source URLs, licenses/boundaries, cutoff, fallback and canonical snapshot digest are
recorded in `tests/fixtures/strict_future_live_field_oracle.json`.

Screen and globally later confirm are disjoint across opponent, lineage, episode, seed, time slice and
market regime. Every foundation/opponent episode is represented from both seats. Confirm remained sealed
by a canonical digest until screen calculation completed. Open-loop summaries trigger refresh and diagnose
drift only; they are not interpreted as closed-loop live strength.

## Results

W/L/T is the primary statistic. Relative margin, lower tail, worst margin, matchup spread and seat symmetry
are diagnostics, avoiding own-bank maximization.

| Foundation | Screen W/L/T | Screen mean / p20 | Confirm W/L/T | Confirm mean / p20 | Confirm seat gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| incumbent | 2/1/1 | +5,932.5 / -6,800 | 2/1/1 | +3,225 / -4,100 | 750 |
| apache-v19 | 1/3/0 | -8,855 / -21,120 | 0/3/1 | -14,025 / -28,100 | 8,350 |
| reactive-optimal | 2/1/1 | +3,475 / -3,100 | 1/3/0 | -3,900 / -9,600 | 8,500 |
| gzmcr | 1/3/0 | -2,100 / -8,100 | 2/1/1 | +1,800 / -2,300 | 5,900 |

Screen ordering is incumbent, Reactive, GzmCR, Apache. Confirm ordering is incumbent, GzmCR, Reactive,
Apache. The known incumbent-over-Apache live-loss anchor is reproduced, but the fallback is not a current
closed-loop refresh. Therefore the oracle result is **inconclusive**, not rejected, and no foundation is
promoted or rejected from this proxy.

## Boundary and compatibility

The measurement script is deterministic and stdlib-only. It validates split overlap, chronology, both-seat
pairing, artifact hashes, immutable snapshot digest, source/fallback provenance and the no-submission
contract. `main.py` and `submission.tar.gz` are unchanged. No Kaggle submission was performed.

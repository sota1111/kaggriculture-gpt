# SOT-2991 C22 live-transfer oracle re-anchor

## Provenance and data boundary

The public Kaggle kernel `beicicc/kaggriculture-c22-exact-reproducibility-control`
(kernel 129552524) was acquired on 2026-08-22 with `kaggle kernels pull --metadata`.
The source identifies itself as Apache-2.0 and is pinned at SHA-256
`bb058dc0dc02ad4a21a07afeef00de631ef1a51ac1a5fbc5443a295b33087ac5`; its
metadata is pinned at `d7c27707ebbe617f49579a87275cbcb4495c0a2e4ac081ca9e56788ec6098fa6`.
The official `kaggle-environments==1.32.7` runtime source is separately pinned at
`bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`.

The C22 source contains a large reproduced action trace. It was used only from a temporary authenticated
fetch directory and is not committed. No private trace, replay JSON, credentials, future outcome, or
submission identifier is an oracle input. The repository stores public metadata, hashes, the pre-registered
panel, and derived episode summaries only.

## Protocol and result

The live blind anchors were fixed before measurement: retained champion `781.5`, Conditional Memory
`600.0`. Screen used C22 under two seeds/market regimes and both seats. Confirm remained digest-sealed
until screen finished, then used two different opponent lineages, episodes, seeds, time slices, and market
regimes, again in both seats. All 16 anchor matches ended `DONE/DONE` at 720 steps.

| Anchor | Window | Mean rank | Mean margin | p20 / worst margin |
| --- | --- | ---: | ---: | ---: |
| old champion 781.5 | screen | 2.0 | -114,710.75 | -152,747 |
| old champion 781.5 | confirm | 2.0 | -2,294,232 | -5,741,351 |
| Conditional Memory 600.0 | screen | 2.0 | -32,861 | -45,964 |
| Conditional Memory 600.0 | confirm | 1.5 | 16,936 | -42,160 |

Champion confirm-minus-screen drift was -2,179,521.25 mean margin and -5,588,604 tail margin.
Conditional Memory drift was +49,797 mean margin, -0.5 mean rank, and +3,804 tail margin. Both anchors'
normalized stability score is 0.0.

## Decision

**Oracle: rejected.** Screen and confirm both prefer Conditional Memory locally, contradicting the actual
`781.5 > 600.0` public ordering. The control therefore exposes that this supposedly live, separated local
panel still cannot be trusted for agent promotion. This is a same-seed/both-seat direct comparison, so the
rejected judgment meets the evidence rule.

**Agents: not evaluated for promotion.** The old champion remains an independent hedge. Conditional Memory's
known public transfer failure is retained as a calibration anchor; it is not resubmitted. No Kaggle submission
or runtime policy change was performed.

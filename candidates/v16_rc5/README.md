# V16-RC5 exact whole-agent evaluation boundary

The public notebook is hash-pinned but declares no license. The exact agent is
therefore not redistributed. `provenance.json` deliberately records a null
artifact and fail-closed promotion decision.

The measurement script accepts an operator-supplied pinned notebook, extracts
`main.py` only into a temporary directory, verifies its hash, and runs disjoint
screen/confirm panels. The source is deleted afterward; the incumbent and
submission archive remain unchanged. No Kaggle submission was performed.

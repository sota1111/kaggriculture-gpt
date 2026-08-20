# SOT-2796 runtime contract

The pinned official Kaggriculture `AGENTS.md` (SHA-256
`0ad68d6de1acd0625177eaf4df9225c3cd9a609fb3efd62e15739b71bc37ddd5`)
requires a root `main.py` with an `agent` function returning exactly `farmer`,
`hands`, and `market`. The matching `kaggle-environments/agent.py` loader
(SHA-256 `9b7682ce9921c8f34080a8be0f7b41598cc12ac7eb14d24e4b707883f25213b6`)
executes the file and selects the last callable in its namespace.

The submitted archive `fae729...c7610c7` defined `component_firing_counts`
after `agent`. Replaying the loader therefore selects that zero-argument
diagnostic function. Its result has diagnostic keys rather than the action
contract, reproducing the all-PASS live behavior. The fix keeps the diagnostic
API for local measurement but defines the public `agent` adapter last.

`SOT-2796-live-runtime-contract.json` replays both immutable SOT-2786 episodes,
both participant seats, and the same observation stream through the submitted
champion and fixed candidate. The champion is invalid on every turn; the
candidate produces contract-valid productive actions in every panel. No
private opponent state, future step, fitted trace, or Kaggle submission is used.

Effective candidate: `main.py:agent`, main.py SHA-256
`b3118e75e5c8e45ed5f82e8c6887b6133ea1dd115463c4fef0ee5b936e6cd1c2`,
submission archive SHA-256
`9436082bbc28bfd4f36f4ec7a73f8c4662fa13e2496014f349bacdb473755870`.

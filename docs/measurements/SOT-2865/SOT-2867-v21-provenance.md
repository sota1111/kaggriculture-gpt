# SOT-2867 V21 late-capital oracle provenance

The upstream source is fetch-only from `https://github.com/Seyamalam/Kaggriculture` at commit `8b8c421eb10634c756583ce10c75189f50c83a72` under the MIT license. Its released `main.py` and `agents/candidate_v21_capital_latch.py` are byte-identical with SHA-256 `0cd14b653102d276c4f902fa3b8c6bd81d869b8ab64c422cb881b9d2346ec639`.

V20 stopped its recovery overlay at step 577. V21 instead keeps that overlay eligible through step 718 and, exactly once at step 577 for each seat, reads only the public player index and both farms' bank values. It latches abstention when `rival_money - own_money <= -5000`; the decision persists and is not recalculated. Upstream reports V18 public rating 2053.6, frozen-corpus wins improving 94/110 to 100/110, untouched live-corpus wins improving 27/30 to 29/30, sealed top-20 remaining 31/40, and a +6.98 mean paired margin across 100 adaptive seeds.

The committed manifest contains identities and source hashes only. Each agent is fetched and executed closed-loop against the repository's deterministic simulator; no recorded action stream is replayed. Screen and confirm hold out opponent artifact/entity, episode, seed, and time, with confirm strictly later. Both seats are present for each entity. Confirm is not executed unless screen has zero champion invalid actions and contract violations. The validator fails closed on private/future/reward/replay, credential, or external-weight fields and on any overlap or provenance drift.

Replay bytes, credentials, private/future fields, and external weights are not committed. No Kaggle submission was performed.

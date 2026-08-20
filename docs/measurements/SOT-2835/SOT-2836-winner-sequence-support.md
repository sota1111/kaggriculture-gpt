# SOT-2836 winner economic sequence-support attribution

The hash-pinned winner-only public dataset was split before analysis by winner
entity, episode, seed, and time. Screen covers both seats across three episodes;
untouched confirm covers a different winner entity and three later episodes,
also across both seats. Confirm was evaluated only after screen reproduced a
non-zero sequence-support gap and all data-contract checks passed.

Across the bounded eight-step prefixes before winner economic actions, champion
first-action support was 0.003024 on screen (992 events) and 0.003699 on confirm
(811 events). The first reproducible unsupported precursor was a task decision:
the winner established `BUILD_PASTURE` at step 1 while the champion selected
`WEST`. At that boundary the public farm had one pasture, no visible animal
tile, no prefix feed balance, and four workers/$500–999 cash on screen versus
five workers/$0–499 on confirm. The invariant is the early pasture/task boundary;
worker count and cash band are contextual ranges, not a fitted causal threshold.

Inventory and feed state are inferred only from same-or-earlier public actions.
Private shed contents, future observations, replay bytes, credentials, and
external weights are excluded. The result is an attribution/support proxy on
winner public states, not causal uplift and not proof that an open-loop replay
reconstructs the champion's live trajectory. No runtime policy was changed and
no Kaggle submission was made.

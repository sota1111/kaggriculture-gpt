# v25 Strict-Future clean-room whole agent

This candidate reproduces only portable, prose-level v25 ideas on the
independent Apache-2.0 Agent Builder foundation. The source notebook explicitly
states that its 719-action backbone was reconstructed from a public replay, so
that backbone and its bytes are fetch-only and excluded under the repository's
provenance gate.

`agent.py` is generated deterministically by `scripts/package_v25_strict_future.py`.
It neither imports nor modifies the incumbent `main.py`, and it needs only the
Python standard library at runtime. The candidate remains default-off and no
Kaggle submission is made by this issue.

The Apache-2.0 license file is reproduced from the independently licensed
foundation package. Attribution and the excluded replay boundary are pinned in
`source.json`.

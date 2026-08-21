# V7 portable hedge candidate

This directory pins the independently evaluated public V7 whole-agent source.
It deliberately does not vendor `main.py`: upstream's Apache-2.0 notice covers
only attributed route portions and explicitly does not license the independently
written controller. Public source availability alone is not a redistribution
license.

Given a user-acquired checkout at the exact commit in `source.json`, build and
verify a standalone offline archive without changing the champion:

```bash
python3 scripts/package_v7_portable_hedge.py \
  --source-checkout /path/to/COK-ZhangZiliang-Kaggriculture \
  --output /tmp/v7-portable-hedge.tar.gz
```

The generated archive contains `main.py`, `THIRD_PARTY_NOTICES.txt`, and
`LICENSE-APACHE-2.0.txt`. It is for local evaluation only until the upstream
author grants a license covering the whole agent. It must not be submitted to
Kaggle or promoted over the repository champion based on public score.

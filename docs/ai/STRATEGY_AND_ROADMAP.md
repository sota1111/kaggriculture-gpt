# Kaggriculture GPT — 統合戦略・ロードマップ

最終更新: 2026-08-23 UTC

対象: Kaggle `kaggriculture` / GPT lineage

この文書は、人間が一枚で現状・確定事項・次の判断を追える統合記録である。機械可読の
[`experiment_ledger.jsonl`](experiment_ledger.jsonl) を置き換えず、ledger、各 cycle の申し送り、
`docs/measurements/`、`docs/ai/` の記録を事実源として要約する。数値は観測時点のスナップショットであり、
非定常な leaderboard の現在値を保証するものではない。

## 0. 性質・制約・評価指標

- Kaggriculture は表形式予測ではなく、720 step の環境で相手と競う **agent / RL・live matchmaking 型**である。
  評価対象は root に `main.py` を持ち `agent(obs)` を公開する単一 `tar.gz` agent で、実行時はネットワーク、
  credentials、外部 replay、追加 weights に依存できない。
- 主 KPI は live field での相対成績（leaderboard rank / rating / public score）である。ただし対戦相手と
  メタが時間とともに変わるため `cv_representative=false`。同一 byte の提出でも public score が時間で変わり、
  public の高得点が将来の live field や private/final field へそのまま転移する保証はない。
- 固定 seed・固定 opponent の local CV は、契約違反、無効 action、介入発火、相対 margin、tail、seat 差、
  screen→confirm drift を診断する proxy であって、champion 昇格を確定する oracle ではない。実例として local
  panel が Conditional Memory や Apache Agent Builder を選んだ一方、両者の live public は `600.0` だった。
- 評価規律は「local で安全性と帰属を確認し、可搬性と provenance を通った独立候補だけを疎に live 観測し、
  旧 champion を hedge として残す」。`inconclusive` は失敗の隠蔽ではなく、非代表 CV から結論を捏造しないための
  正しい終端である。
- **provenance gate**: source URL/version/hash、明示ライセンス、stdlib/offline 実行、固定 action tape、
  replay/clone 再構成、private/future data、weights、runtime dependency を提出前に監査する。無ライセンス source、
  replay 由来の固定経路、埋め込み action table は fetch-only とし、verbatim 再配布・提出・champion 化を禁止する。
  公開された一般原理だけを独立に clean-room 実装する場合も、元 executable と同一だとは主張しない。

## 1. 現状サマリ

| 項目 | 現状（2026-08-23 UTC 時点の記録） |
| --- | --- |
| champion | `main.py` の incumbent を維持。C95、Conditional Memory、Apache clean-room などは live 昇格を棄却し、working champion を置換していない |
| champion の live 観測 | 時間変動を伴い、おおむね `779.4`、`781.5`、`798.9`、`806.4`。直近の直接比較に使った incumbent ref `55690743` は `792.7`（概ね 774〜815 帯という運用上の把握と整合） |
| 直近 challenger | Apache-2.0 C95 exact、ref `55701484`、public `600.0`。incumbent `792.7` に対し `-192.7` のため live promotion は rejected |
| 実 leaderboard 順位 | 直近 cycle 群では表示中 top 20 未満（圏外）が継続 |
| leaderboard 首位 | 観測により `3134.4`〜`3157.7`、公開ノートの公称値は約 `3164`。champion との差は約 2,300 点 |
| champion 方針 | incumbent を構造独立 hedge として温存。Kaggle 提出物と repo の champion を混同せず、候補 probe 後も復元・維持する |

したがって現状は「local 指標をさらに押し上げれば 2500+ へ連続的に近づく」状態ではない。最大のボトルネックは、
公開上位の得点源に replay/clone 人工物が多いことと、現在の local oracle が live 相手分布の ordering を再現できない
ことの二つである。

## 2. 試行錯誤の履歴と結果

| 時期 / cycle | 主な試行 | 結果と学び |
| --- | --- | --- |
| 初期 oracle / policy cycles | submission contract、有限 horizon 経済、distribution shift、shared-market competitive oracle、robust online planner、opponent-aware scarcity | runtime・無効 action・cash-only reward の基礎を整備し、複数の local 軸を promoted。一方、beam planner、固定 regime selector、mixed-farm などは direct A/B の tail/confirm で rejected |
| public opponent / replay cycles | COK・lonespear 系を hash/license 固定し、entity/seed/time/both-seat holdout、authenticated replay identity、scheduler、fertilizer、livestock、shed protectionを評価 | 評価 provenance と一部 runtime component は改善したが、fresh live episode では all-PASS/低 rating など local↔live drift が顕在化。以後は local margin を live strength と同一視しない |
| architecture / sealed cycles | compact policy、multi-step planner、capacity dispatcher、layout、late-capital、tomato/egg/feed 系を screen→sealed confirm で評価 | 発火しても主要 KPI が同値・悪化する軸は rejected。実ゲームで発火しない軸は無理に rejected/CLOSED とせず inconclusive とし、confirm を未開封で保持 |
| public whole-agent 探索 | V16-RC5、Strict-Future v27、V111、V16-RC5-R5A、HarvestForge-X 3094、Moon Counts Melons、Kaito、V7 などを provenance 監査し、verbatim または clean-room 候補を分離 | V111 clean-room は same-seed screen mean margin `-91,990.5`、confirm `-88,756.5` で rejected。R5A と Hamburger V27 も isolated confirm で rejected。V16-RC5 / Strict-Future は local closed-loop が強くても無ライセンスの固定 route/action trace のため fail-closed。HarvestForge-X 3094 と Moon 系も無ライセンス部分を vendoring せず、default-off/fetch-only または限定 clean-room に留めた |
| oracle 再アンカー | authenticated current-top replay、C22 control、Strict-Future live-field panel、official-engine economic oracle、current-field Stage A/B | C22 panel は既知 live ordering `incumbent 781.5 > Conditional Memory 600.0` を逆転して oracle 自体が rejected。Strict-Future は current replay refresh 不可で inconclusive。current-field Stage B は incumbent を選んだが、trajectory 不足と final holdout 未開封のため診断用途に限定 |
| 採用＋提出＋観測への転換（PR #418 以降のドクトリン） | `cv_representative=false` では研究だけで止めず、provenance を通る強い whole-agent を exact artifact として governed submit し、incumbent を hedge 保存 | Conditional Memory `600.0`、Apache clean-room `600.0`、C95 `600.0` と、local 高評価が live へ転移しないことを実測。C95 は incumbent `792.7` に対し `-192.7` で rejected。この実観測により「local CV を昇格 oracle にする」方針から「live 分布へ oracle を再アンカーする」方針へ移行 |

V16-RC5 の verbatim probe（SOT-2988）は特に重要な転換点だった。静的監査で `_ACTIONS` に 720 step の
固定 action table（展開後約 106 KB）が埋め込まれ、公開 submission `55440039` の replay 3 件から schedule を
再構成した旨が source に記載され、かつライセンス宣言がないことを確認した。禁止条件に抵触するため gate を呼ばず
提出 0 本で中止し、champion を維持した。

## 3. 確定した結論

1. **公開 2500+ / 約 3164 の大半は、その時点の field を replay/clone から再構成した固定 action table・固定 route
   に強く依存する人工物である。** V16-RC5 は 720-step table と replay 再構成を直接確認した代表例である。
   この種類の得点は過去 field 固有で、進化する live/private field へ転移せず、無ライセンスなら再配布もできない。
   ゆえに「自作 agent が 2500+ に届かない」ことを、そのまま公開上位 agent の採用失敗とは解釈しない。
2. **provenance は性能 gate より先に置く。** 明示ライセンス、hash、source boundary、固定 tape/replay/clone の有無、
   offline contract を一つでも満たさなければ verbatim 採用しない。public score や local 勝率で例外を作らない。
3. **現在の fixed local oracle は live promotion oracle ではない。** Conditional Memory、Apache、C95 の local-positive / live-600、
   および C22 の ordering inversion が反証である。`cv_representative=false` のため、厳密な local screen/confirm 後も
   `inconclusive` が続くのは規律どおりであり、結論不足を偽の promotion/rejection で埋めない。
4. **live 観測は必要だが、public-best 選抜はしない。** provenance を通る candidate の fingerprint を固定し、reserve、
   spacing、daily cap を守って一度観測する。結果は非定常な一標本として扱い、incumbent hedge を必ず残す。
5. **champion は現 incumbent のまま。** C95 exact は local readiness を満たしたが live `600.0` で棄却済み。
   V111、R5A、Apache clean-room、Conditional Memory、Hamburger V27 も新しい opponent-distribution evidence なしに再試行しない。

## 4. 今後の方針

### A. 可搬・licensed whole-agent の採用＋live 観測（役割A）

- 新しい公開 agent は、まず provenance gate を通す。明示ライセンス、source/artifact hash、stdlib/offline、単一 root
  archive、固定 replay/action tape 非依存をすべて満たすものだけを exact candidate とする。
- 条件を満たし、incumbent と構造的に異なる強い候補が見つかった場合は、local contract・same-seed/both-seat safety
  を確認後、artifact と effective-config fingerprint を固定して governed submit する。結果が悪くても調整して再提出せず、
  live transfer evidence として ledger に残す。
- 無ライセンスだが一般化可能な考え方がある場合は、source executable を配布せず、原理を限定した clean-room 軸として
  別 lineage にする。元の高 public を clean-room 実装の根拠にはしない。

### B. 評価 oracle を live 相手分布へ再アンカー（役割B）

- 最新の opponent / lineage / episode / seed / seat / time slice を cutoff 付きで取得し、screen・confirm・final の identity を
  分離する。replay bytes、credentials、private/future state は commit せず、hash と集約結果だけを保存する。
- 最初の合格条件は「candidate を選ぶこと」ではなく、既知の live ordering と drift を再現すること。`incumbent > live-failed
  candidates` を再現できない panel は promotion に使わず oracle 自体を rejected / inconclusive とする。
- current-field trajectory を安全に取得できる場合、official-engine の terminal inventory、crop tile-day、CARE/feed payback、
  market impact の恒等式へ接続し、planning-to-trajectory gap と live 低下を分離する。取得できなければ推測で因果化しない。

### C. hedge と探索規律

- incumbent を常時 hedge 保存し、candidate probe のために repo champion や working archive を恒久上書きしない。
- 既存 rejected 軸は、新しい opponent distribution、明示ライセンス、異なる causal intervention などの新証拠なしに再試行しない。
- local tuning が飽和したら、oracle 再構築 → transfer-gap 帰属 → architecture 変更 → 新しい licensed external knowledge の順に
  escalation する。`inconclusive` の多さ自体を blocker にしない。

### マイルストーン

1. **M0 — provenance inventory**: 現存 whole-agent 候補を licensed exact / clean-room / fetch-only / rejected に分類し、
   replay/action-table 検査結果と hash を揃える。
2. **M1 — live-distribution oracle v1**: cutoff-frozen current-field cohortで既知 live ordering を再現し、再現できなければ
   oracle の失敗理由を記録する。
3. **M2 — trajectory attribution**: 安全に得られる範囲で current-field trajectory と engine-economic identities を接続し、
   transfer gap の上位要因を特定する。
4. **M3 — licensed candidate observation**: provenance gate を通った構造独立 whole-agent を一つだけ fingerprint 固定で提出・観測し、
   incumbent hedge と直接比較する。
5. **M4 — converge portfolio**: 締切接近時のみ、live evidence と構造差に基づき incumbent + 独立 hedge の最終候補を選ぶ。
   public 最大値だけで二枠を埋めない。

## 5. 参照

- 機械可読の全実験履歴: [`docs/ai/experiment_ledger.jsonl`](experiment_ledger.jsonl)
- 実測 artifact 群: [`docs/measurements/`](../measurements/)
- runtime / archive contract: [`SOT-2796-runtime-contract.md`](../measurements/SOT-2795/SOT-2796-runtime-contract.md)
- current-top replay provenance: [`SOT-2782-authenticated-replay-cv.json`](../measurements/SOT-2781/SOT-2782-authenticated-replay-cv.json)
- V111 same-seed / confirm: [`SOT-2982-v111-economic-core.json`](../measurements/SOT-2981/SOT-2982-v111-economic-core.json)
- V16-RC5 transient portability gate: [`v16-rc5-screen-confirm.json`](../measurements/SOT-3002/v16-rc5-screen-confirm.json)
- Strict-Future live-field oracle: [`strict-future-live-field-oracle.md`](../measurements/SOT-3005/strict-future-live-field-oracle.md)
- C22 ordering inversion: [`SOT-2991-c22-live-transfer-oracle.md`](../measurements/SOT-2986/SOT-2991-c22-live-transfer-oracle.md)
- current-field sealed evaluator: [`current-field-sealed-evaluator.md`](../measurements/SOT-3013/current-field-sealed-evaluator.md)
- C95 live result: [`SOT-3013-final.md`](linear/SOT-3013-final.md)
- 関連 Linear: [SOT-2981](https://linear.app/sota-dev/issue/SOT-2981)、
  [SOT-2988](https://linear.app/sota-dev/issue/SOT-2988)、
  [SOT-3028](https://linear.app/sota-dev/issue/SOT-3028)
- ドクトリン導入の履歴: control-plane PR #418、恒久ドクトリン PR #422（方針の由来。実測値の事実源は上記 ledger / measurements）

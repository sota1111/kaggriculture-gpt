# Solo Worker Report — SOT-3032

## Summary

Adaptive Replay Agentの公開snapshotを一時領域へ認証取得し、URL、kernel ID、最終実行時刻、notebook/metadata/embedded-agent/decoded-tableのSHA-256を固定した。licenseは未宣言で、719-step中690 stepがnon-PASSの固定action tableをentrypoint・翌step preemption・weed recoveryが参照するため、verbatimを禁止してfetch-onlyとした。固定scheduleを除いたadapter群は独立whole-agentを構成しないためclean-room候補は作らず、sealed confirmを開かなかった。incumbentとsubmission artifactは変更しておらず、Kaggle提出もしていない。

## Changed Files

- `candidates/adaptive-replay-audit/` — provenance-only descriptorと境界説明
- `scripts/audit_adaptive_replay_provenance.py` — fail-closed監査validator
- `tests/test_adaptive_replay_provenance.py` — boundary/hash drift focused tests
- `docs/measurements/SOT-3032/adaptive-replay-provenance.json` — machine-readable監査結果
- `docs/ai/experiment_ledger.jsonl` — cycle 6 provenance rejection記録
- `docs/ai/linear/SOT-3032.md` — issue tracking/acceptance記録

## Commands Run

- `kaggle kernels list --competition kaggriculture ...` — source特定
- `kaggle kernels pull junaid512/02-adaptive-replay-agent --metadata` — transient取得
- `python3 scripts/audit_adaptive_replay_provenance.py --source-dir /tmp/...` — PASS
- `python3 -m unittest tests.test_adaptive_replay_provenance -v` — 3 PASS
- `python3 -m compileall -q main.py candidates scripts tests` — PASS
- `python3 -m unittest discover -s tests -q` — 278 PASS、2 optional skip
- `python3 scripts/validate_submission.py submission.tar.gz` — invocation error（validatorはPython source pathを要求）
- `python3 scripts/validate_submission.py main.py` — PASS
- `git diff --check` — PASS

## Acceptance Criteria

- [x] provenance判定が明示済み
- [x] verbatim可否をlicense/構造証拠で決定
- [x] clean-room候補の成立可否を判定。候補なしのためablation/発火logはN/A、sealed confirmは未開封
- [x] Kaggle提出なし

## Risks

- Kaggle metadataはnumeric version/licenseを公開していないため、取得時刻とcontent hashesでsnapshotを固定した。
- 本結論は性能rejectではなくprovenance/portability gateでのreject。上流が明示license付きで再公開された場合は再監査が必要。

## Linear Report

PR merge後にCompletion Reportを投稿する。

## Acceptance: PASS

## Next Action: READY_FOR_REVIEW

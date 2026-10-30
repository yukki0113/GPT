# RaceNote v0.5.6 — 予想スレッド引継ぎ / 初回BTDAY受入運用

更新 2026-10-30。**運用区分: 実戦試験候補（正式昇格は初回BTDAY成功後）**。

## 守るべき設計

- BTDAY / FORWARD のLLM判断、Prediction Freeze、Confidence Freezeは単一共通処理。印選定はv0.5.5 r6同様、全頭比較LLM著述。Confidenceは勝ち切りの確信度(A/B/C)、対象外Z。
- Predictionは `decision_core` 内に `prediction_audit_comment` を含み、Confidenceを入れない。
- Prediction Freezeをmainに永続化・verifyした後にだけ、凍結済み◎を見て `confidence_review`（勝ち切り根拠、強敵との比較、敗北シナリオなど）を独立著述する。Confidence Freeze完了まで結果/配当/当日市場を開かない。
- BTDAY：後から結果照会・評価。新聞短評清書工程は起動しない。
- FORWARD：PACI専用T1とBTDAY共通の二段階Freezeは接続。両Freeze完了後の新聞短評清書/掲載工程は別マイルストーン（未導入）。
- 旧v055のセッション/Frozenに手を触れない。v056実装をv055の既存ルートへ挿し込まない。

## 現時点の入口

- v056専用T1 Orchestrator: `.github/workflows/racenote_v056_t1_orchestrator.yml`
- リクエスト: `horse-racing/jrdb/backtests/requests/orchestrator-v056/<unique>.json`。JSON形式 `{"mode":"NEXT","selection_id":null}` または `{"mode":"EXISTING","selection_id":"BTDAY-NNNN"}`。
- `NEXT` は2025年Historical Warehouseから日を1つ選び、共有 `racenote_v056_btday_turn1_shared.yml` でT1作成後、`racenote_v056_racezip_delivery.py` でArtifact `racenote-v056-orchestrator-BTDAY-NNNN` を公開する。
- v056 T1パス `horse-racing/jrdb/backtests/BTDAY-NNNN/YYYYMMDD/v056`。
- 新T2の機械的実行器: `src/racenote_v056_turn2_two_phase.py`。LLM著述した全レースの `incoming/llm_decisions.json` 提出後 `racenote_v056_llm_prediction_freeze.yml` → mainの `frozen/day_handoff.json` と `frozen/records.json` を照合。
- 独立したLLM Confidenceを `incoming/llm_confidence.json` 提出後 `racenote_v056_llm_confidence_freeze.yml` → mainの `confidence_frozen/day_handoff.json` と `turn2_summary.json` を照合。
- フローは1ルートずつ。GitHub Actions起動と正常終了、実際のmain反映をそれぞれチェックする。CIの構造テスト成功だけではBTDAY成功とみなさない。
- 指示 `T2_ONLY` は次BTDAYの先行T1を起動しないモード。初回v056の受入ではまず単独T1→T2_ONLYが安全。

## 予想スレッドが最初にすべきこと

1. mainにv056 tools/workflowsがmerge済みか、CI実行結果と直近SHAを検証。未mergeならT1を起動しない。
2. 2025年Warehouseの未使用適格日を新v056 orchestratorで選定。既存v055 T1 Orchestratorと**リクエスト先を混同しない**。
3. NEXTのreserve/t1/deliver各job・Artifact・index/全レースSHAを監視。失敗時は原因を修正して同一BTDAYを再開し、日付を勝手に変更しない。
4. 全36RのReaderでLLM独立予想・圧縮短評を生成。全レースを揃えてPrediction Freezeを確定。凍結済みPredictionを再予想・変更しない。
5. 全36Rの◎についてLLMが独立したConfidenceを構造記録付きで判断。Confidence Freezeを確定。結果はこの後の既存cohort gateに従って解禁。
6. 両Freezeのsession, contract, roster, SHA, commit, workflow成功、Confidence件数、印の一貫性を報告。2段階目の完了前に結果を開かない。

## 未検証として扱うもの

- 2025年Warehouse実データのv056 T1→36R著述→二段階Freeze一気通貫は未実施。
- FORWARD PACI T1は `racenote_v056_forward_turn1.py` と `racenote_v056_forward_paci_t1.yml` で実装。日次の本番入力受入は未実施。新聞清書・PWA連携は未実装・未受入。指示書 `RACENOTE_V056_FORWARD_PACI_RUNTIME_20261030.md` を参照。
- T1の直後に生成したReader ZIPを受けたLLMの実予想作業は、予想スレッド側の責務。
- `config/racenote_forecast_logic_current.json` の古いresearch pointerに依存せず、初回実験は明示的v056のworkflow/contractを指定する。成功までcurrentを一括変更しない。

## 切戻し

v056の新規起動を止め、旧v055 r6の旧root / Freeze / workflowは保持する。いずれのFrozenも上書きしない。

# RaceNote v0.5.6 — BTDAY-0187 W/R/U/D 引継ぎ（2026-11-11）
 
## 次スレッドの最優先事項
最新GitHub `main`を再取得してBTDAY-0187の正式二段階Freeze、SHA、W/R/U/D専用Shadowの作成状況を確認する。**結果照会前に**未閲覧条件が成立するかを確認すること。現時点の状態を将来にも当てはめない。

### 最終確認時の状態
- BTDAY-0187 = **2025-08-03 / 36R / A8・B21・C1・Z6**
- Root: `horse-racing/jrdb/backtests/BTDAY-0187/20250803/v056/`
- `turn2_summary.json`: `TURN2_COMPLETE`, `authoring_quality=PASS`, Prediction `PREDICTION_FROZEN_CLEAN_BLIND`, Confidence `CONFIDENCE_FROZEN_CLEAN_BLIND`。
- Prediction SHA256: `77844a4c71fed62fb29ee2c5a17e74e7fb9c69f9cc7e2482a0e1d01e7be2980f`
- Confidence SHA256: `fcca87d75dd74fa3cfb05e520aa91f4a706a5f13db373ec4a2720526d1b988dd`
- `result_opened=false`, `target_market_opened=false` は**元Freezeのメタデータ**。その後の閲覧有無は別確認。
- `research/wrud/incoming/review.json`, `research/wrud/frozen/seal.json` とも確認時点で存在せず。
- Git treeを確認した範囲で2025-08-03の旧BTDAYは見当たらず。調査時点のHEAD `22bf3020b2c502ed11753916240ad6813a5494e9`。再開時に再確認。
- 0186 = 2025-07-26 / 36R / A9・B17・C4・Z6、通常Freeze PASS、Shadow未確認。

## 直前スレッドで完了
- 同日リプレイのConfidence比較：0175→0183（2025-03-29）は◎同一28/36、Confidence同一18/36、B→A8・C→A1。新A9Rは全て◎同一。0169→0184（2025-11-08）は◎同一30/36、Confidence同一25/36、B→A3・A→B4。
- 0183〜0185のA26件で`relative_advantage`と`final_grade_reason`が全件同文。正式予想・判定は変更しない。
- 独立W/R/U/D Shadow Freezeツール・Actions・運用仕様・比較監査レポートをPR [#2527](https://github.com/yukki0113/GPT/pull/2527)でマージ。commit [905a0a8](https://github.com/yukki0113/GPT/commit/905a0a8ca91b3ea76dccda000fd29cda8f7e330d)。
- セルフテストと0185テンプレート生成がActions [#42964712021](https://github.com/yukki0113/GPT/actions/runs/42964712021)でPASS、PRの3種検査もPASS。**実レビュー投入→GitHub Actions→Shadow seal読み戻しのE2Eは未実施**。
- 0183〜0185は事前のShadow Freezeがなかったので、過去回を前方Shadowの標本に遡及算入しない。0183と0175、0184と0169は同一日であり独立日として二重計数しない。

## 必読の正本
- [W/R/U/D運用仕様](20261111_RACENOTE_WRUD_SHADOW_FREEZE_PROTOCOL.md)
- [Confidenceリプレイ監査](../reports/20261111_RACENOTE_A_BOUNDARY_REPLAY_0175_0183_0169_0184.md)
- [研究ツール](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/src/racenote_v056_wrud_shadow.py)
- [Shadow専用Workflow](https://github.com/yukki0113/GPT/blob/main/.github/workflows/racenote_v056_wrud_shadow_freeze.yml)
- [0187 Freeze概要](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/backtests/BTDAY-0187/20250803/v056/turn2_summary.json)

## 実行手順・制約
1. 最新`main`を取得し、0187の正式Prediction/Confidence Frozen recordsと両handoff・SHA、36Rの◎一致を再検証。既存Shadowファイルの有無を再確認。
2. 対象日結果・払戻・市場をまだ閲覧していないことを実際に確認。**既に結果が知られている場合は盲検前方Shadow扱いを中止**し、後方診断と区別する。システムは人間の未閲覧を独立証明できない。
3. 実験として成立する場合のみ、`python horse-racing/jrdb/src/racenote_v056_wrud_shadow.py --mode template --root horse-racing/jrdb/backtests/BTDAY-0187/20250803/v056 --output horse-racing/jrdb/backtests/BTDAY-0187/20250803/v056/research/wrud/incoming/review.json`。
4. 結果・市場を参照せず**平地30R全件**にW（1着への勝ち筋）、R（○▲等との比較優位）、U（敗戦条件とその影響）、D（固有の事前根拠）、`shadow_reason`とShadow A/B/Cを独立著述。Z6RはZのまま、説明欄null。正式Confidence・◎・印・既存Freezeは不変。
5. `evidence_attestation`を事実に基づいて記録し、`--mode validate` PASS後にincoming/review.jsonを`main`にコミット。
6. GitHub Actionsの起動・初動エラー・成功を確認し、`research/wrud/frozen/records.json` と `seal.json` を`main`で読み戻しSHAを検証。既存Sealは上書き禁止。**Seal確認前に結果照会しない**。
7. ここまで完了後にJRDB SED/HJCで結果照会・A対Shadow Aの検証を実施。独立開催日20件程度を初回目標とし、回収率改善は未実証。

## 次のスレッドへの初回指示
「GitHub `yukki0113/GPT` の `horse-racing/jrdb/docs/racenote/research-work/instructions/RACENOTE_BTDAY0187_WRUD_HANDOFF_20261111.md`に従い、BTDAY-0187の現状確認と、可能なら結果照会前のW/R/U/D独立Shadow Freezeを実施してください。正式Prediction・Confidence・過去Freezeは絶対に変えず、Actions実行・保存後の読み戻しまで確認してください。」

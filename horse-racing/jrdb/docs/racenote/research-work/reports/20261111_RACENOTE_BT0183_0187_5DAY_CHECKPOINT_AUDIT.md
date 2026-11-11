# RaceNote v0.5.6 — BTDAY-0183〜0187 5日チェックポイント監査

作成：2026-11-11 / Status: **OFFICIAL FREEZE PASS; WRUD SHADOW NOT YET SUBMITTED; RESULTS NOT QUERIED**

## 目的
2026-11-11に実施された初回5BTDAYチェックポイントの状態を監査し、「正式Prediction/Confidence Freeze」と「新設W/R/U/D研究Shadow Freeze」の達成を区別する。結果照会は実施しない。

## 正本チェック
GitHub `main` の各 `backtests/BTDAY-xxxx/YYYYMMDD/v056/turn2_summary.json`、`frozen/records.json`、`confidence_frozen/records.json` を読み戻した。

| BT | 日付 | R | 標準平地（A+B+C） | A | B | C | Z | Freeze/◎一致 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 0183 | 2025-03-29 | 36 | 35 | 9 | 14 | 12 | 1 | PASS 36/36 |
| 0184 | 2025-11-08 | 36 | 29 | 8 | 16 | 5 | 7 | PASS 36/36 |
| 0185 | 2025-10-26 | 36 | 30 | 9 | 15 | 6 | 6 | PASS 36/36 |
| 0186 | 2025-07-26 | 36 | 30 | 9 | 17 | 4 | 6 | PASS 36/36 |
| 0187 | 2025-08-03 | 36 | 30 | 8 | 21 | 1 | 6 | PASS 36/36 |
| 合計 | | **180** | **154** | **43** | **83** | **28** | **26** | **PASS 180/180** |

全5回は `TURN2_COMPLETE`、`PREDICTION_FROZEN_CLEAN_BLIND`、`CONFIDENCE_FROZEN_CLEAN_BLIND`、`result_opened=false`、`target_market_opened=false`、通常著述品質PASS。ここでの市場・結果未閲覧は**Freeze側の記録上の宣言**であり人間の既知情報の独立証明ではない。

## W/R/U/Dレビュー状況
- A43/43件に `winning_case`、`primary_rival`、`relative_advantage`、`main_defeat_scenario`、`risk_assessment`、`final_grade_reason` の**既存Confidence本文**が存在。全標準平地154件でも主要欄は欠損0。
- **A43/43件で `final_grade_reason` と `relative_advantage` が完全同文**。両者は役割が異なり、同文は説明の分離不十分を示唆する。文章一致のみで正式Aを誤判定と断定しない。
- **5回とも** `v056/research/wrud/` が存在せず、専用 `incoming/review.json` と `frozen/seal.json` は未確認。つまり独立W/R/U/D Shadow判定・Freezeの実施件数は **0**。
- 専用Workflow `.github/workflows/racenote_v056_wrud_shadow_freeze.yml` は `incoming/review.json` のGitHub mainへのPushで起動する。通常のPrediction/Confidence Freezeには組み込まれておらず、BTDAYを5回回すだけでShadowが自動生成される運用ではない。
- BT0183〜0185はW/R/U/D導入前のFreezeであり、後から研究用結果前Shadowを完了済みとすることはできない。0186/0187も専用レビューなし。過去の結果アクセス状態・レビュー担当者の知識を検証できないため、実際の未閲覧を確認せず、後付けの宣誓を埋めることは禁止。

## 独立性・重複日
- 0183（2025-03-29）は0175と同日。
- 0184（2025-11-08）は0169と同日。
- 0185（2025-10-26）、0186（2025-07-26）、0187（2025-08-03）は、現在のmainで同日BTDAYの重複を確認していない。
- したがって**新規の独立開催日としては最大3日**。0183/0184は判定再現性研究に有用だが、独立開催日として二重計数しない。

## 判定分布の注意点
A43/180=23.9%、標準平地だけではA43/154=27.9%。Cは0183で12/35だったが0187では1/30。開催・出走構成が異なるため、これだけではConfidenceの品質・精度の向上／悪化を結論できない。正式A数の目標・調整は設けない。

## チェックポイント判定
**PASS**：通常BTDAYの5回連続Prediction/Confidence Freeze、全180Rの本命一致、通常Confidenceの主要根拠の存在、監査可能な正本。

**NOT YET PASS**：W/R/U/Dの独立著述・専用Freeze・SHA読み戻しによる5日Shadow E2E、Shadow Aの実成績対照。Shadowとしての実験記録は0/5BTDAY。

## 次の工程
1. 既存 `20261111_RACENOTE_WRUD_SHADOW_FREEZE_PROTOCOL.md` に従い、結果未参照を実際に担保できる新BTDAYで、通常Confidence Freeze後・結果照会前に、**全標準平地RのW/R/U/Dを別著述**する。
2. `review.json` をコミットし専用GitHub Actionsの結果、`frozen/records.json`、`frozen/seal.json` をGitHub mainで読み戻してから結果解禁。
3. 最初の1回でE2Eを監査し、以後5独立BTDAY分のShadow比較を収集する。既存0183〜0187の古い結果を未検証のうちに照会せずに温存するかは、盲検取り扱いと標本重複を明示したうえで判断する。
4. W/R/U/Dによる勝率・ROIの改善、旧Aからの判定昇降の妥当性は**未検証**。正式予想・自信度・既存Freezeの改変はしない。

参照：`20261111_RACENOTE_A_BOUNDARY_REPLAY_0175_0183_0169_0184.md`。

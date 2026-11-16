# RaceNote v0.5.6 BTDAY-0182〜0191 W/R/U/D Shadow監査（2026-11-16）

## 原則

- 全10件がPrediction / Confidence 二段階Freeze済み（TURN2_COMPLETE）。いずれも正式予想・Confidenceは不変。
- W/R/U/Dは事前の勝ち筋・対抗比較・敗戦条件・固有証拠を独立著述する研究用Shadow。結果・払戻・対象日市場はこのレビューで参照していない。
- 結果未参照の宣誓はレビュー担当者の申告であり、他者による過去の閲覧までは独立証明しない。通常Freeze時点のresult_opened=falseも後続の未閲覧を証明しない。

## Shadow Seal検証済み

| Selection | 対象日 | R | 公式A/B/C/Z | Shadow A/B/C/Z | Seal |
|---|---|---:|---|---|---|
| BTDAY-0186 | 2025-07-26 | 36 | 9/17/4/6 | 7/18/5/6 | [Seal](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/backtests/BTDAY-0186/20250726/v056/research/wrud/frozen/seal.json) |
| BTDAY-0187 | 2025-08-03 | 36 | 8/21/1/6 | 5/24/1/6 | [Seal](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/backtests/BTDAY-0187/20250803/v056/research/wrud/frozen/seal.json) |
| BTDAY-0188 | 2025-03-01 | 36 | 16/14/4/2 | 6/16/12/2 | [Seal](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/backtests/BTDAY-0188/20250301/v056/research/wrud/frozen/seal.json) |
| BTDAY-0189 | 2025-01-19 | 24 | 5/15/1/3 | 1/17/3/3 | [Seal](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/backtests/BTDAY-0189/20250119/v056/research/wrud/frozen/seal.json) |
| BTDAY-0190 | 2025-10-18 | 36 | 13/15/2/6 | 3/24/3/6 | [Seal](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/backtests/BTDAY-0190/20251018/v056/research/wrud/frozen/seal.json) |
| BTDAY-0191 | 2025-04-12 | 36 | 15/18/2/1 | 1/30/4/1 | [Seal](https://github.com/yukki0113/GPT/blob/main/horse-racing/jrdb/backtests/BTDAY-0191/20250412/v056/research/wrud/frozen/seal.json) |
| 合計 | | 204 | 66/100/14/24 | 23/129/28/24 | |

- 0187は既存Sealを読み戻しただけで変更なし。
- 0186・0188・0189・0190・0191は今回レビューを作成し、ActionsでSeal生成とmain読み戻しを確認。
- 0188は阪神9Rのshadow_reason文字数不足で初回Actions失敗。補強後の再実行成功を確認。

## 事前Shadow対象外

| Selection | 対象日 | 事前Shadowにできない理由 |
|---|---|---|
| BTDAY-0182 | 2025-01-05 | A研究で対象日の結果を既に参照済み。新たな事前盲検Shadowとは宣誓不可。 |
| BTDAY-0183 | 2025-03-29 | 運用規約が0183〜0185への後付け前方Shadow認定を明示禁止。BTDAY-0175と同日リプレイ。 |
| BTDAY-0184 | 2025-11-08 | 同じ後付け禁止。BTDAY-0169と同日リプレイ。 |
| BTDAY-0185 | 2025-10-26 | 同じ後付け禁止。 |

## 補足

- 6件合計の研究用Shadowは204R。同一日を重複計数しない。
- 公式Aの件数変化は性能改善の根拠とはならず、凍結後に結果を別途照会して初めて評価できる。
- A/B/Cの遷移、勝率、信頼区間、馬券収支、最終オッズを別々に分析する。
- 契約参照：horse-racing/jrdb/docs/racenote/research-work/instructions/20261111_RACENOTE_WRUD_SHADOW_FREEZE_PROTOCOL.md

## Seal records_sha256

- BTDAY-0186: 76e1ea5ad47c95cd85e95066c4b15629d67c86e5b8ea900cf20d1f3d606e0986
- BTDAY-0187: 3d181e521fd7e90a5d36e62eec440498f4a8adf5dcd10ca59b7a76a939c6fa8a
- BTDAY-0188: ff9a82c9c218e30ffe79ea1c186ae3e1f5d2eb7418769e5f56cdbf84f538538a
- BTDAY-0189: fa3e7f9d11dbf01c67698d5b6120f07fde50f58d496fd1352af8fe5a8fcfc284
- BTDAY-0190: 218c7966c212f04e7cc8eb84f7671a6a28acbb6ef76ca0097704cfefc670ccdd
- BTDAY-0191: c43d1b24167d05d318221cfc93a3a55aa62a36e47cfa86739df78efddb361204

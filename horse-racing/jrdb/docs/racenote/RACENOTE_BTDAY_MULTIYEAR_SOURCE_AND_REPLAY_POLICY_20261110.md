# RaceNote BTDAY — 複数年抽選と再予想の運用境界（2026-11-10）

## 方針（予想スレッド）

- BTDAYの抽選候補を2025年Historical Warehouseに恒久限定しない。2026年PACIも、対応する**検証済みT1入力経路が実装・受入済み**なら抽選母集団に含める。
- PACI保存日とBTDAY台帳の完全な日次同期は必須ではない。同期は運用上の別責務とする。
- 同一対象日を異なるBTDAY IDで繰り返し予想してよい。予想スレッドは当該日付の対象結果・配当・当日市場を両Freeze前に読まない。検証側の成績・結果と予想側のアクセスを分離する。
- `selection_cycle` は履歴・監査上のメタデータ。予想の可否や品質の機械判定にしない。未使用1周目の優先や、2周目を自動的に不適格とする運用は要求しない。
- 検証の独立性については、**予想スレッドからの結果非参照**と**モデルの過去同日経験の影響**を区別して記録できる。周回数だけを根拠に「予想不可」「不正な予想」とは判定しない。
- 日付ごとの抽選履歴・元データ区分・selection ID・Freeze SHAは保持する。既存Freezeを書き換えず、公開済みの対象結果を入力へ混入させない。

## 現行実装の受入ギャップ（修正完了を意味しない）

2026-11-10時点の以下の実装は、2025年Historical Warehouse専用である。

1. `src/racenote_v056_t1_orchestrator.py` の `choose_next()` が2025年以外を抽選対象外にし、`pick_days(...,source_mode="historical_warehouse")` を指定。
2. 同ファイルの `read_selection()` が2025年・historical_warehouseだけを受入。
3. `.github/workflows/racenote_v056_btday_turn1_shared.yml` が2025年のBAC/KYIを固定取得し、2026年・PACIを拒否する。
4. `docs/racenote/RACENOTE_V056_BTDAY_PREDICTION_THREAD_HANDOFF_20261030.md` は2025年のみを現行の入口として説明している。

これらを取り除く**だけ**では2026年を選んだ直後にT1が失敗し、BTDAY IDを予約済みとして残すおそれがある。

## 実装受入条件

1. 2025年Historical Warehouseおよび2026年PACIについて、元データ区分に従う明示的なT1入口を用意する。2026年PACIはDrive正本のファイル実体・正しい日付・SHA・CRC・KYIの完全性を受入検証し、JRDBへの安易な直接再取得で代替しない。
2. 2026年BTDAYを組み立てる際、2025年専用アーカイブを流用しない。対象日より未来の結果や市場・配当を予想入力へ混入させない（as-of-exclusive）。
3. 抽選前に、その候補日を実際にT1まで処理できる入力・資料の受入を検証する。不足があれば候補を除外し、誤った予約を作らない。初回と再利用を均等な抽選候補として扱い、未使用優先を暗黙に挿入しない。
4. `NEXT` / `EXISTING` / `STATUS` / `T2_ONLY` の再入可能性、Selection/Session一致、Reader Clean Blind、T1 Artifact、予想・Confidence二段階Freezeを2025/2026双方でE2E受入する。
5. 正式受入までは2025年の現行T1を壊さず、2026年が選ばれるのに生成不能という中途半端な状態をリリースしない。

**状態:** 運用方針は決定。2026年BTDAYのT1実装・E2E受入は未完了。

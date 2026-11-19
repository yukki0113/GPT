# BRDB 馬場別実績・条件一致比較 v0.4 candidate — 2026-11-19

**RESEARCH ONLY / NO PRODUCTION OR RACENOTE/PWA AUTHORISATION**

## 目的と基準入力

父産駒の馬場別実績を同一の芝・ダート、競馬場、コース、距離で比較する。事前の想定馬場はPACIから補完せず、RaceNote予想にも渡さない。`brdb_going_condition_compare.py` は既存JRDB Analysis v1.4 Parquetの `fact_entry_result_lite` を読む。RawのSED/PACIを再パースしない。

今回取得・監査した正本manifest: `analysis-v1_4-postrace-20261115-01`、全2016〜2026年の11 partitions（2016-01-05〜2026-11-15、manifest合計523,812行）。**11/11の年次ファイルでraw SHA256・sizeがmanifestと一致**。これは入手・整合性の実績であり、まだDuckDBを使用した全期間の集計成功を意味しない。対象2026-11-15分析では `race_date < 2026-11-15` を適用する。

当初のSED/PACI単日対比の研究版は有用だが、全年次データに結び付く正本Analysis v1.4が既に実装・保存されているため、履歴全体の主経路として後者を採用する。

## 分析条件

- 絶対に `race_date < target_date` とし、出走確定当日の結果は使用しない。対象日以降の別年partitionsは照合するが集計対象に入れない。
- 芝・ダート区別を対象と同じ値に固定。障害・他区分と混合しない。
- `track_condition_code` のJRDB公式12分類を「良」「稍重」「重」「不良」に対応、比較用に「良」対「道悪＝稍重/重/不良」に統合。ただし個別の馬場4区分比較は将来実装するため、適性と同一視しない。
- スコープは `VENUE_COURSE_DISTANCE`, `VENUE_DISTANCE`, `ALL_VENUES_DISTANCE`, `VENUE_BAND`, `ALL_VENUES_BAND` の5段階。異なる距離帯の無分別混合を行わない。5段階の数字は重複しているので加算しない。
- `abnormal_code=0` の正常完走に限定。取消・除外・中止・降着等を合算しない暫定分母で、正式な「出走数」定義は別途受入が必要。
- 比較母数、勝ち数、3着内数、率、複勝率差（百分点）を返す。どちらかが0件の場合差をnull。各母数20未満は`LOW_SAMPLE`。小標本の好成績を捨てず、あくまで観測事実として残す。
- 各 `findings` は機械的比較であり、表示/予想許可=false。因果・道悪適性・指数の推定は禁止。
- 現行Analysis v1.4の血統プロフィールの当時存在保証は未検証のため、全体を`AS_OF_UNVERIFIED`とする。

## データ・実行契約

`--common` には前段v0.1の実18頭共通分析JSON、`--manifest` には読み戻し検証済みAnalysis v1.4 manifest、`--objects-root` にはそのmanifestに記載された `objects/fact_entry_result_lite/year=YYYY/<sha>.parquet` ファイル群を置く。ファイルは年・サイズ・SHA・パス・全行数・主キーを検証する。DuckDBは `tools/data-storage/` のpinに従う。

```
python horse-racing/brdb/src/brdb_going_condition_compare.py \
  --common /private/common_analysis.json \
  --manifest /private/analysis_v14/manifest.json \
  --objects-root /private/analysis_v14 \
  --output /private/going_v04.json \
  --receipt /private/going_v04_receipt.json
```

## 検証範囲と未完了

- 本環境での11年次Parquet SHA照合: 11/11 PASS。Pythonドメイン回帰: 6/6 PASS。
- 本環境のDuckDB依存修復はネットワーク制限で失敗。Parquet実集計・合成ParquetテストはCIへ委譲。**未実行をPASSと記録しないこと**。
- v0.4は独立sidecar。v0.3の近親/馬場入力契約は変更しない。正式レビュー生成やRaceNote入力には接続していない。
- 全出走馬の実測成績は非公開ファイル内でのみ計算し、GitHubやPR本文には個別の馬別集計結果を置かない。
- 今後の受入: DuckDB実データ全期間replay、分母定義、同日再現性、歴史UKC時点、馬場4状態と今回想定馬場の比較方式、複勝率のベースライン比較。

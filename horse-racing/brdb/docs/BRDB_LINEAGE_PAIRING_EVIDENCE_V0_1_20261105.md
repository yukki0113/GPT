# BRDB ③ 父系×母父系の組合せ条件別実績 — v0.1 研究検証

- 作成日: 2026-11-05
- Status: **RESEARCH ENGINE IMPLEMENTED / REAL 8-HORSE REPLAY PASS / NOT PREDICTION-SAFE**
- ソース: `../src/run_brdb_pairing_evidence.py`
- テスト: `../tests/test_brdb_pairing_evidence.py`
- 入力: ①②の `brdb-sire-bms-field-evidence-v0.2` JSON、JRDB Analysis v1.4 CURRENT（SHA-pinned Parquet）。
- 出力: ③の `brdb-lineage-pair-evidence-research-v0.1` JSON、出走馬1頭につき5条件の根拠。
- ⑤契約: `BRDB_INTEGRATED_BLOOD_REVIEW_CONTRACT_v0_2_CANDIDATE.md` に将来接続。⑤判定の実装や既存Review v0.1更新ではない。

## 1. 何を「組合せ」とするか

`sire_line_code × broodmare_sire_line_code` の**JRDB公式コード同士**の一致で過去の実出走馬を抽出する。

- 父個体×母父個体ではない（ニックスの断定禁止）。
- 父系・母父系の分類コードは「父の父系と母父の父系」の組合せであり、母方の血統全体・母の全祖先ではない。
- 例: `1206 × 1503` と `1503 × 1206` は**区別**する。
- コードは正式な4桁の文字列で照合し、地域・国籍ラベルを推測しない。
- 欠損・不正コードは `UNKNOWN_LINEAGE`。馬名からの類似補完をしない。
- ①の父個体／②の母父個体別実績と、③の系統の集計母集団は重なるため、単純な加算・投票は不可。

## 2. 各馬に返す5条件

①で確定した検索条件を共有し、**全5段階で対象の芝ダ区分を固定**する。

| 優先度 | スコープ | 例: 東京芝2000m |
|---|---|---|
| 1 | VENUE_COURSE_EXACT | 東京・芝・同一コースコード・2000m |
| 2 | VENUE_DISTANCE | 東京・芝・2000m |
| 3 | VENUE_BAND | 東京・芝・中距離帯（1800〜2399m） |
| 4 | ALL_VENUES_DISTANCE | 全場・芝・2000m |
| 5 | ALL_VENUES_BAND | 全場・芝・中距離帯 |

各条件で、(a) 組合せの成績、(b) **父系単独**の成績、(c) **母父系単独**の成績、(d) 条件全体の基準値を**同じ出走分母**から算出する。出走回数と一意馬数、勝利/3着内、率とWilson95%区間、基準値との差、標本状態を保持。

組合せと父系単独・母父系単独の複勝率差（percentage points）も記述値として返す。組合せに固有の相乗効果が存在するという証明ではない。**実績が0件の場合、率はnullであり0%としない。**

## 3. 時点・母集団の保護

- 過去10年を初期窓とし、**対象レースの日付未満**に限定。対象レース当日以降の結果を含めない。
- 分母は取消/除外（JRDB code 1/2）を除く実出走。中止（3）・失格（4）・降着（5）・再騎乗（6）は出走数に含める。勝利・3着内はコード0/5かつ公式着順の記録を使う。
- 個体や同一馬の繰り返し出走は独立サンプルではないため、一意馬数も返す。
- **重要な制限:** Analysisの過去年別UKC血統コードについて、当該過去レース当日に取得できていたという配信時点保証は未確認。出力で `pedigree_temporal_status=HISTORICAL_LINEAGE_PROFILE_ASOF_UNVERIFIED`、`prediction_safe=false` を必須にした。
- 2016〜2025年の別マート `P0-2` は後年選択の静的血統スナップショットであり**本エンジンの根拠源に採用しない**。仮に過去結果のas-ofを満たしても、それだけで歴史的血統属性のas-ofは証明されない。
- そのため今段階は**記述研究用途に限定**。正式な「開催前の③血統根拠」として⑤に採用するには歴史的プロフィールのas-of検証が必要。

## 4. 実レース検証

2026-11-01 東京5R・芝2000m（PACI261101.zip、8頭）の①②出力を受け取り、同日より前のJRDB Analysis履歴に照会した。レース8頭は**7種類の組合せ**。

次は「東京芝2000mの同一コースコード」の観測値であり、あくまで**記述統計**。

| 馬番 | 父系×母父系コード | 組合せ走数 | 一意馬数 | 3着内回数 | 複勝率 | 件数状態 |
|---|---|---:|---:|---:|---:|---|
| 1 | 1206×1503 | 180 | 168 | 50 | 27.8% | DESCRIPTIVE |
| 2 | 1206×1107 | 20 | 15 | 8 | 40.0% | LOW_SAMPLE |
| 3 | 1206×1503 | 180 | 168 | 50 | 27.8% | DESCRIPTIVE |
| 4 | 1503×1206 | 171 | 157 | 45 | 26.3% | DESCRIPTIVE |
| 5 | 1206×1103 | 54 | 43 | 18 | 33.3% | DESCRIPTIVE |
| 6 | 1206×1106 | 43 | 41 | 18 | 41.9% | DESCRIPTIVE |
| 7 | 1108×1206 | 9 | 8 | 4 | 44.4% | LOW_SAMPLE |
| 8 | 1206×1108 | 43 | 39 | 11 | 25.6% | DESCRIPTIVE |

同条件の全体基準複勝率は約26.8%（同条件全実出走1,347件）。ただし、**同一レース内でこの表を順位・印・予想に読み替えない**。No.2/7は比率が高くても低サンプル扱い。DESCRIPTIVEは暫定件数区分に過ぎず「相性が良い」評価ではない。

比較例: No.6（1206×1106）の同条件複勝率41.9%は、父系1206全体との差が+11.2ポイント、母父系1106全体との差が+5.79ポイント。異なる種牡馬や年代、出走選択、人気などを統制した因果効果ではない。

## 5. 性能／テスト

- 環境: ローカルCPython3.13、DuckDB1.1.3、JRDB Analysis v1.4 CURRENTの11年分ParquetをSHA確認。
- 初回実行: 約**751ms**。追加3回の実測: **540 / 487 / 405ms**（OSキャッシュ等に依存、Google Drive転送時間を除外）。
- 同一レースの8頭について、全組合せをGROUP BY一括集計。父系・母父系単独の比較母集団も同条件で集計。
- ローカル合成テスト5件 PASS（出走数の取消/中止、芝ダ固定、5スコープ、未来結果除外、ゼロサンプル、未知コード、SHA改ざん、入力contract/as-of）。GitHub反映版のCI実行結果は別途確認が必要。

## 6. 残る実装境界

- ③ **記述統計の抽出と比較出力**を研究モジュールとして実装した。**条件ごとの配合特性・ニックスを確定する規則は未実装**。
- `③ pair` に `AS_OF_UNVERIFIED` が残る間、⑤出力でこの資料を検証済みの好材料・悪材料として採用してはならない。⑤candidateには参考エビデンスと未検証状態として繋げられる。
- ③の系統別結果は父個体×母父個体の代替ではない。今後、④兄姉・近親の観測根拠とともに⑤の統合解釈を検証する。
- BRDB CURRENT、Blood Review v0.1、RaceNote、PWA、新聞の本番実装は変更しない。

## 7. 再現手順

```bash
python horse-racing/brdb/src/run_brdb_pairing_evidence.py \
  --sire-bms-json /private/tokyo5_sire_bms_evidence_v02.json \
  --analysis-root /private/analysis_v1_4_root \
  --output /private/tokyo5_pairing_evidence.json
python -m unittest discover -s horse-racing/brdb/tests -p test_brdb_pairing_evidence.py -v
```

JSON個票とJRDB Raw/Parquetは私的データとしてGitHubへは掲載せず、集計レポートのみ公開する。

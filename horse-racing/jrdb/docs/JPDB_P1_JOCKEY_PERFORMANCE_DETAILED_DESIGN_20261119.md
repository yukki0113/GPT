# JPDB P1 — 騎手実績DB 詳細設計 v0.1（2026-11-19）

**状態: DETAILED_DESIGN / NOT PRODUCTION APPROVED。** 2023-01-01以降の中央競馬・平地を対象に、RaceNoteのバックテスト日以前の騎手実績を返すための設計。これはP1の詳細設計であり、P2条件別統計・P3騎手能力推定・P4 RaceNote本番接続の完了宣言ではない。

## 0. 正本、前提、設計の目的

- 既存の読み取り実装: `src/jpdb_history_reader.py` v0.1（2023–2025のSED、`rider_history(target_date, jockey_code)`）。2026年データは未接続。
- 入力正本: 修復済みWarehouse `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix` のBAC/KYI/SED（2023–2025）。受入済みBAC/KYI/SEDの結合、Course Masterの平地9,991レース結合を再利用する。Source Hash/manifestは必須。
- 利用時点: ユーザー承認済み `JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1`。**過去SEDの確定値はそのレースの翌日以降利用可能だったと仮定**する。配信タイムスタンプや後日修正を厳密再構成しない。この仮定は出力に残し、過去の配信事実として主張しない。
- 全ての履歴取得で `2023-01-01 <= source_race_date < target_date D` かつ `source_race_date >= max(2023-01-01, D-3暦年)`。当日の早いレースも使用しない。年跨ぎ・閏日も暦日計算する。
- 歴史SEDの**実騎乗者**とターゲットKYI/PACIの**予定騎手**は独立。2023–2025のKYI/SEDの差異731件は正式乗替り件数と見なさない。`FINAL_KYI_PROXY`と`OBSERVED_PRE_RACE_PACI`は区別する。
- **目標**: (A) 騎手の過去の騎乗件数、着順・条件実績を再現可能に提供、(B) 騎乗馬の質・人気・機会の差と騎手の能力を混同せず、P2/P3研究に進める、(C) RaceNoteの各出走馬に読み取り専用の出典つき特徴量を渡す。

## 1. データモデルと責務

**歴史事実レイヤー（immutable JPDB candidate）**：物理複製を前提にせず、受入済みSEDをDuckDBで読み、必要なBAC/KYI/Course Masterにキー結合する。`race_key_raw × horse_no`を一意な歴史騎乗候補キーとする。実騎乗者はSEDの`jockey_code`（文字列5桁、先頭ゼロ保存）。対象レースのコードは別の予想前KYI/PACIから取得し、歴史事実に混ぜない。

| ファミリー | 実際に定義されている列 | 利用目的 / 注意点 |
|---|---|---|
| SED | `race_key_raw`, `horse_no`, `race_date`, `jockey_code`, `abnormal_code`, `finish`, `field_size`, `surface_code`, `distance_m`, `track_condition_code`, `race_class_code`, `grade_code`, `final_popularity`, `final_win_odds`, `race_running_style_code`, `trainer_code` | 原則として過去の結果と結果時点の観察項目。最終オッズ・走法は過去レースに限定。 |
| BAC | `venue_code`, `distance_m`, `surface_code`, `turn_code`, `layout_code`, `course_code`, `race_class_code`, `grade_code` | レース固有条件。SEDへの結合は一対多を禁止。 |
| KYI | `jockey_code`, `blood_registration_no`, `trainer_code`, `cancel_flag`, `base_win_odds` | 過去レースの予定情報・血統/調教師の照合補助。**そのレースのSED実騎乗者をKYI予定騎手で上書きしない**。 |
| Course Master | `course_key`, `geometry_key`, `physical_version_id`, `physical_valid_from`, `physical_valid_to_exclusive` 等 | コースIDと物理属性の時点有効性を別判定。未検証属性NULL保持。 |

**必要なマテリアライズを行う場合の正規形**：

1. `jpdb_riding_fact_v1`: 一行=歴史の`(race_key_raw,horse_no)`。結果・騎手ID・race_date・レース条件・出典世代と列の取得状態、実騎乗可否・結果分類。ライセンス付き実レコードは非公開配置。
2. `jpdb_jockey_daily_aggregate_v1`: `(as_of_date_exclusive,jockey_code,population_filter_id,dimension_set_id,dimension_value,window_id,source_generation)`を一意にする集計。長期正本コピーは不要。RaceNote対象日の必要騎手だけを集計、任意のキャッシュには源SHA・SQL definition hash・as-ofを必ず保存。
3. `jpdb_reader_response_v1`: 予想/バックテストに渡す集計JSON。出典・未観測・信頼性・適用条件を付す。後述のP2/P3研究指標を未承認のまま含めない。

データ世代更新、Parquet/DuckDB、SHA検証は既存`tools/data-storage/`を使い、JRDBのfixed-length Reader `src/jrdb_raw.py`を複製しない。

## 2. 母数と異常区分 — v0.1からの明確な切り分け

**従来のReader `JPDB_FLAT_NORMAL_FINISHERS_DIAGNOSTIC_V1` は変更しない**。その`normal_win_rate=wins/normal_finishes`は「正常完走に限定した割合」であり、一般的な出走ベースの勝率とは呼ばない。

次期設計候補 `JPDB_FLAT_RIDE_START_V1_CANDIDATE` （実装・正式受入前）は次のとおり：

| `SED.abnormal_code` | 観測ラベル | 出走機会の母数候補 | 正常完走着順の集計 | 扱い |
|---|---|---|---|---|
| `0` または空欄 | 通常結果 | 加算（ただしfinishの範囲を検証） | `1 <= finish <= field_size`のみ | 範囲外は`INVALID_FINISH`として率の分母に無断追加しない |
| `1` | 取消 | 除外 | 除外 | `entries`には残し`nonstarter_count`へ |
| `2` | 除外 | 除外 | 除外 | 同上 |
| `3` | 中止 | 加算候補 | 完走着順対象外 | 騎乗機会には含めるが着順評価と混同しない |
| `5` | 降着 | `REVIEW`（出走自体は発生したと推定） | `REVIEW` | 2023–2025に1件あり、最終着順・入着率の扱いを現物確認してから凍結 |
| `4`, `6`, 未定義/NULL | 未観測・未出現コード | `REVIEW` | `REVIEW` | 決して通常結果として補完せず、`unknown_status_count`と監査へ |

`declared_entries`、`nonstarter_count`、`actual_starts_candidate`、`normal_finishers`、`dnf_count`、`demotion_review_count`、`unknown_status_count`を混同しない。`actual_starts_candidate`は本番勝率の確定母数とまだ呼ばず、上記のレビュー保留を解決した別`population_filter_id`で凍結する。

採用候補の実績値は `wins`（正常・着順1）、`top3`（正常・着順1–3）、`top2`（正常・着順1–2）、`sum_finish_position`、`normal_finish_rate`、`start_basis_win_rate`、`start_basis_top3_rate`。分母が0、レコード矛盾、未承認の母数は**NULL/UNAVAILABLE**。無効・欠測を敗退扱いで代用しない。

**不変条件**：全区分件数の総和=対象entries。正常完走内では`wins <= top2 <= top3 <= normal_finishers`。芝＋ダート=全平地。対象日当日以降の件数=0。異常5の未分類がある間は正式な「出走ベース指標」に昇格不可。

## 3. 何を集計するか：段階的な指標群

| ID | 指標群 | 主な切り口 | 判定・スコープ |
|---|---|---|---|
| `CORE` | 出走・正常完走・勝ち/連対/複勝・中止・取消/除外・最終騎乗日 | 全平地、芝、ダート | P1の最優先。現行Readerに既存の一部あり |
| `RECENT` | 直近90/365日、全履歴3年の件数・着内率・直近空白日数 | 同一騎手×対象日 | 90/365は**試験候補**、有効期間上限2023にclamp・明示 |
| `VENUE` | 場別実績 | 競馬場コード01–10 | BAC一意結合、場外・障害対象外 |
| `SURFACE_DISTANCE` | 芝/ダート、距離帯、距離完全一致 | 異なる帯を重ねず、帯境界は設定ファイルで版管理 | 初期は距離の連続値・完全一致を保存、最適な帯の定義はP2で凍結 |
| `CLASS_GRADE` | クラス・格別 | JRDB原コード、必要時に正規化別version | クラス替わり、格別母数の薄さに注意 |
| `GOING` | 馬場状態別 | JRDB原コード→既存`track_condition_bucket` | 芝/ダート別々に集計、粗い条件は版管理 |
| `COURSE` | コースID/有効な物理属性別 | `course_key`, `geometry_key`, 上り坂、直線、方向 | Course Master時点有効JOIN必須、NULL/物理PARTIALは残す |
| `PACE_STYLE` | 過去レースのペース・脚質 | SED `race_pace_code`, `race_running_style_code` | **結果から得た記述統計のみ**。対象当日への脚質/ペースは予測値として別ソース |
| `POPULARITY` | 人気・オッズ帯ごとの騎乗成績 | 過去レースSED `final_popularity`, `final_win_odds` | 過去の騎乗馬の質/市場期待値の記述的代理。対象当日の最終オッズは絶対参照禁止 |
| `PARTNER` | 騎手×調教師、騎手×馬の継続実績 | `trainer_code`、`blood_registration_no` | 実際の組合せの再現性・母数確保・ID一致を確認。相性の因果主張は禁止 |

**優先順位**：P1で`CORE`と基本`SURFACE`・期間境界を受入→P2で`VENUE`・`SURFACE_DISTANCE`・`CLASS_GRADE`・`GOING`・`COURSE`を比較→P3で交絡調整と頑健性検証。条件の直積をすべて前計算しない（疎なセルと多重比較を増やすだけ）。

## 4. 得意・不得意の推定: 統計と騎乗馬の質を分ける

**第一層: 生の実績**。N/W/Top3、母数明示、完全な標本数と期間を返す。人気馬を多く任される騎手の高勝率を「騎手だけの能力」とは呼ばない。

**第二層: 比較対象をそろえた記述的差**。例：同一条件（芝/ダート×場×クラス、過去の単勝人気階層など）で、当該騎手の勝/3着内率－同条件の同時点以前の全騎手ベースライン。クラス・人気階層の定義は事前に固定し、基準標本も`race_date < D`で作る。自己騎乗を含むベースラインとの依存は明示し、原則騎手自身を除いた比較群を併記する。

**第三層: 馬質・機会を考慮する研究**。馬の事前能力、過去の騎乗歴、クラス、距離、年齢、枠・出走頭数、騎乗機会の選択過程など、**ターゲット日以前に取得できる特徴量のみ**で期待成績を算出し、実績との差を残差として比較する。過去の`final_win_odds`による市場期待との差は観察研究で利用可だが、当日最終オッズを入力にした事前予想と混同しない。条件付き残差は騎手の因果効果を証明しない。

- 期待値計算では各歴史レース`r`の基準を`source_date < r.date`で構築する**逐次時点外予測**か、時間順に厳密な学習/検証分割を使う。対象D以前の過去レースであっても、モデル作成にそのレース自身の結果や後続の履歴を入れてから「予測値」として戻さない。
- 期待勝利数`E_w=sum(p_win_pre_race)`、残差`O_w-E_w`、期待3着内数`E_3=sum(p_top3_pre_race)`、残差`O_3-E_3`を候補にする。ただし`p`の予測精度・校正は未検証。ここに架空の確率値や係数を設定しない。
- 競走単位の依存/馬・厩舎・騎手継続性を考慮した時系列検証、標本信頼区間、層別の多重比較/縮小推定を必須とする。単勝回収率は市場・配当の混入と外れ値が大きいため優先指標にしない。
- 過去レースの結果から定義した`race_running_style_code`や`race_pace_code`を**当該レースの事前期待値の説明変数**に混入させない（結果側での群別診断には使用可）。

## 5. 少数標本、欠測、主張レベル

各セルに `sample_n`, `population_n`, `coverage_ratio`, `history_days`, `last_observed_date`, `unclassified_n`, `sample_support_status`を持つ。

`sample_support_status`候補:
- `NO_HISTORY`: 有効履歴ゼロ。成績率はNULL。
- `INSUFFICIENT`: 件数はあるがセルの評価基準に未達。参考値は出せるが「得意/不得意」ラベル禁止。
- `DESCRIPTIVE_ONLY`: 記述に十分な母数だが能力効果の保証なし。
- `COMPARATIVE_RESEARCH`: 比較条件、期間外評価、信頼区間と補正が通った研究に限定。
- `REVIEW_REQUIRED`: 不明異常コード・Course物理時点不明・予想データ源不明等。

**数値閾値は研究用の初期候補**：各条件セル`n<30`を`INSUFFICIENT`、`n>=30`を記述候補とする。ただし30件をもって優位性や高信頼としない。95% Wilson区間（割合の記述用）、計測標本の時系列偏り、複数条件探索による偶然発見の補正を併用する。30はCourseStatsのgeometry利用閾値との整合を考慮した初期案であり、JPDBとして正式採用する前に標本分布と感度検証が必要。縮小推定の強さ`k`や時間減衰半減期、長短窓の重みを本段階で恣意的に確定しない。

`NO_HISTORY`と`INSUFFICIENT`は分ける。前走リンクの不明は初出走扱いしない。状態が`REVIEW_REQUIRED`の場合は、スコア算出に採用しない。

## 6. データ集計・クエリパターン

```text
RaceNote / independent backtest context: target_date=D, target race_key, horse_no,
                                   scheduled_jockey_code, target_entry_source
 -> JPDB Reader validate(D, jockey_code, population_version)
 -> validate immutable accepted Warehouse generation + SED SHA
 -> enforce [max(2023-01-01,D-3y), D), turf/dirt
 -> SED actual jockey_code group + BAC course/venue join only if needed
 -> rows→complete category counts→by-surface/by-venue/... aggregation
 -> compare against condition population with same cutoff if requested
 -> emit descriptive metrics, support, source and assumption labels
 -> optional P2/P3 research layer under separately approved version
 -> RaceNote adapter only after P4 integration gate
```

1回のRaceNote 1Rにつき全頭分は、**各騎手に都度3年分を再スキャンするのではなく**候補騎手コードをまとめてパラメータ化して一括集計し、対象日D・同一source世代・同一populationをキャッシュキーにする。Reader v0.1の単体APIを維持し、後続に`rider_histories(target_date, jockey_codes)`のバッチAPIを追加する計画。馬番→騎手コードの紐付けは対象のKYIから受け取り、同じ騎手の重複出力は整理する。

履歴データの各行を結果側の`SED.jockey_code`で集計することは変更しない。前走騎手の続投/変更を計算する際は別の`KYI.previous_link`→SED/ZED結果キー解決と馬ID検証を要する。

## 7. Reader応答契約案（P1.1候補・未実装）

```json
{
  "schema_version": "jpdb-history-response-v1-candidate",
  "target_date": "2025-11-15",
  "target_jockey_code": "01234",
  "target_entry_source": "FINAL_KYI_PROXY",
  "asof_policy": "JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1",
  "source_generation": "<accepted generation ID>",
  "population_filter_id": "JPDB_FLAT_NORMAL_FINISHERS_DIAGNOSTIC_V1",
  "history_from_inclusive": "2023-01-01",
  "history_to_exclusive": "2025-11-15",
  "overall": {
    "declared_entries": 0,
    "normal_finishers": 0,
    "wins": 0,
    "top2": 0,
    "top3": 0,
    "normal_win_rate": null
  },
  "conditions": [],
  "support": {"status": "NO_HISTORY", "sample_n": 0, "validated": false},
  "historical_release_attested": false,
  "source_manifest_sha256": "<manifest SHA-256>"
}
```

**これは型と境界のサンプルであり実騎手の値ではない。** 既存Readerの`all_flat`/`by_surface`はそのまま保持。レスポンス拡張は別`schema_version`を立てる。条件集計は`dimension_set_id, value, n, wins, top3, population_filter_id, source_status, physical_version_status`等を持つ配列とし、条件値未定義を空文字等で埋めない。ユーザー表示には母数、期間、条件、信頼度、出典前提を必ず同伴。

## 8. バックテスト受入条件

- 受入済みSED 2023–2025で歴史件数合計142,737、平地/障害分離、年度ごとのハッシュ一致を再監査。対象期間末日Dの翌日のレコードはゼロ。
- `CORE`集計（騎手×期間×芝/ダート）の件数が原SEDの独立SQLと一致し、正常完走/取消除外/中止/降着/未知コードを互いに排他的に分類。欠測/矛盾はfail closed。
- 同一`(race_key_raw,horse_no)`の多重計数なし。BACおよびCourse Master結合でレコード数が増えない（過去の平地9,991レースの結合監査を継承）。
- 2023年境界、閏日、同日レース、未来データ、0件、騎手コード5桁、先頭0、存在しない騎手、2026未対応、manifest改ざんの合成テスト。
- 従来`jpdb-history-reader-v0.1`の戻り値・値を無断変更しない。新区分は異なる`population_filter_id`と`schema_version`を使い、移行比較を含める。
- 比較基準・人気帯・特定馬/調教師・コース物理属性は**対象日時点の有効範囲**で再評価し、後からの結果・市場情報のターゲット混入禁止。過去の最終オッズはその過去レースの説明変数としてのみ許容。
- **2026 YTDは未接続**。増分の原本と更新方式が受入されるまで2026対象日をReaderが黙って通さない。
- RaceNoteの既存の予想・印・Confidence・Freeze・正式入力は変更しない。P4で手動・自動ハンドオフを決め、バックテストに対してスコア有効性の前向き評価をするまで予想重みに入れない。

## 9. 実装フェーズと終了基準

| 段階 | 納品物 | 終了基準 |
|---|---|---|
| `P1.1` | 母数仕様v1、区分のunknown監査、Reader単体/バッチAPI、期間別CORE、マニフェスト・テスト | 出走件数・条件件数・不変条件一致。異常5の扱い明確化 |
| `P1.2` | 2026日次SED差分・重複解決・CURRENT読み取り専用ソース統合 | 2025/2026境界で二重計数/漏れ0、実2026 YTD監査 |
| `P2` | 芝/ダート×場×距離×クラス等の記述統計、Course属性結合、支持率と不確実性 | 条件分布と標本サイズの実測、物理属性有効性 |
| `P3` | 人気/馬質を考慮した条件比較、時系列out-of-time検証 | 交絡・多重検定・選抜バイアス明示、効果の過大評価防止 |
| `P4` | RaceNoteから対象日/騎手コードを渡すAdapterと独立検証 | ターゲットKYIソース区別・情報漏洩0・Freezeへの影響0 |

**設計上の重要な非結論**: P1の記述指標を騎手の能力と直接同一視しない。P2の「得意条件」も生勝率だけで断定しない。P3で補正済み研究指標が安定するまで、予想スコア/印/馬券推奨への自動加点は行わない。

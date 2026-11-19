# JPDB P2 — 条件別騎乗実績 / Course Master Reader v0.1（2026-11-19）

**状態: P2 READ-ONLY RESEARCH CANDIDATE / REAL SOURCE E2E PASS。予想投入・本番公開は未承認。**

## 1. 正本と対象

- 条件軸Reader: src/jpdb_p2_condition_reader.py
- BAC/Course Master物理属性Reader: src/jpdb_p2_course_master_reader.py
- 基盤: P1.2 JPDBPerformanceReader2026。不変のP1.1/P1.2 APIに追加する独立Readerであり、既存の戻り値を変更しない。
- 2023–2025: 受入済み Warehouse jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix のSED 142,737件、BAC 10,365レース。受入済みSHA manifestの検証必須。
- 2026: Driveで選択したSED 97 ZIP（42,185件）とPACI 97 ZIPのBAC member（3,066レース）。各ZIPの容量、CRC、SHA、member SHA、行数、race_date、race_keyを検証。PACIの97日集合はSEDと完全一致。
- Course Master: RRDB Phase3 [run 38370479179](https://github.com/yukki0113/GPT/actions/runs/38370479179) の固定SHA seed（master177行、JRDB mapping433行、geometry57行）。

対象は2023-01-01以降のJRA平地。利用する歴史レース日は、基準日Dより厳密に過去。期間は3暦年、365日、90日の3窓を2023-01-01で切り上げる。歴史騎乗者は結果SEDのjockey_code。現在の予定騎手はこのReaderでは解決しない。

## 2. 条件集計

| Dimension set | 内容 | 認証境界 |
|---|---|---|
| VENUE | 競馬場01–10 | JRA平地 |
| SURFACE_DISTANCE_EXACT | 芝・ダート×距離m完全一致 | 距離帯は未凍結 |
| CLASS_GRADE_RAW | クラス・グレード原コード | 空欄は補完しない |
| GOING_RAW | 芝・ダート×馬場状態原コード | bucket未凍結 |
| COURSE_RAW_CODE | 競馬場・芝ダート・course/turn/layout原コード | 物理コース認証には使わない |
| COURSE_KEY | BAC→Phase3 stable course key | mapping確定・時点有効 |
| GEOMETRY_KEY | BAC→Phase3 geometry key | master/geometryのversion整合 |
| TURN_DIRECTION | コースの方向 | 物理PARTIAL |
| FINAL_SLOPE | 最終直線上り坂フラグ | 物理PARTIAL |
| COURSE_SIZE | コース規模 | 未観測はNULL |
| FINAL_STRAIGHT_M | 最終直線長 | 未観測はNULL |

全条件セルは出走件数、正常完走、勝ち・連対・3着内、取消/除外/中止/降着/未知、観測日、条件別母数、coverage_ratio、sample_support_status、出典・物理属性状態を持つ。各dimensionの合計は同騎手・同期間のP1.2 COREに一致する。不整合はfail closed。n<30は初期研究上INSUFFICIENTの目安であり、「得意」「不得意」の能力ラベルを出さない。

## 3. BACによるコース同定（重要）

SEDのcourse_codeをCourse Masterの物理キーとして直接使わない。実測でSED原コード直接JOINは2025年462騎乗、2026年1,117騎乗が未対応だった。一方、**レース正本BAC**（2023–2025受入Parquet、2026のPACI内BAC）でrace_key_rawを基準に結合すると、2023–2026の全平地レースをPhase3 mapping_status=CONFIRMEDに解決できた。

BAC条件の venue × surface × distance × turn × layout × NULL正規化済みcourse_code をPhase3 mappingに完全一致させ、物理masterとgeometryのphysical_version_id一致、両者の2023+有効期間を検証。コースJOINによる多重化・欠落・無効epochは停止。現Phase3 masterは全件physical_data_status=PARTIALであり、過去完全版course_version_id台帳ではない。欠測値は埋めない。

## 4. 実データE2E（2026-11-19）

- 全SED **184,922件**、平地 **179,436騎乗**、2026平地 **40,945騎乗**。BACとSEDのrace_key、date、surfaceの欠落/不一致、JOIN fanoutは0。
- 平地BACは2023年3,329レース、2024年3,327、2025年3,335、2026年2,960、合計**12,951レース**。物理epoch・対応キーは全件PASS。
- 12騎手×4基準日（2025-11-16、2026-01-04、2026-06-13、2026-11-16）×3期間の独立SQL照合。Raw条件5軸：**12,207セル/36,621比較 PASS**、物理条件6軸：**16,146セル/48,438比較 PASS**。
- 実データのPythonテスト：Raw **3/3 PASS**、Course Master **3/3 PASS**。
- 物理属性のNULLを保持：最終直線長38,946騎乗、コース規模7,406騎乗。最終直線上り坂フラグは欠測0。
- 監査正本：[集計・SHAのみのJSON](evidence/jpdb_p2_conditions_course_e2e_20261119.json)。独立監査コードは src/jpdb_p2_real_condition_e2e_audit.py と src/jpdb_p2_course_master_e2e_audit.py。ライセンス付き原データのGitHub掲載なし。

## 5. 非認証項目・後続工程

**PASSの範囲は固定スナップショットの条件別・物理属性別の記述統計と時点有効性を確認したReaderであり、本番予想効果ではない。**

- 過去SEDの実際の配信時刻は未証明。承認済み JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1 を維持しstrict as-ofは認証しない。
- 物理epochは2023年以降の保守的な検証期間。過去すべてのcourse_version改修履歴を証明しない。
- 距離帯、馬場粗分類、連続更新CURRENT、公式降着コード5の本番母数処理は未凍結。
- P3で馬質・人気・騎乗機会などの交絡、時系列外検証、少数標本の不確実性、多重比較を確認するまで、高い生勝率を騎手能力とは呼ばない。
- RaceNote予定騎手、印、Confidence、Freeze、PWAへの接続・変更は行っていない。

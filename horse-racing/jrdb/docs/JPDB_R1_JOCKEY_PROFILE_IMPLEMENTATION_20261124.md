# JPDB R1 — 予定騎手条件プロファイル実装・固定実データ受入 (2026-11-24)

**R1 FIXED_SOURCE_RESEARCH PASS / R2 NOT IMPLEMENTED / PREDICTION SAFE = FALSE / PRODUCTION NOT APPROVED.**

共通目的: [JPDB × BRDB 独立Evidence方針](racenote/RACENOTE_JPDB_BRDB_INDEPENDENT_EVIDENCE_POLICY_20261120.md)。既存の実績馬評価を単純補強するのでなく、過去走以外の比較根拠を提供し、新馬戦を別コホートとして研究する。P3因果能力認証をR1の前提としない。

## 1. 正本・契約

- `src/jpdb_r1_profile_builder.py`: P1.2/P2 raw/physical Readerをそのまま使用。実騎乗者は過去SED、今回予定騎手は固定PACI KYIのjockey_code（reference_jockey_codeではない）。対象race_key_raw × horse_no × horse_idを保持。全KYI登録頭を保持しBAC field_sizeと照合、予定騎手ID不正・重複・不明レース・SHA/CRC不一致は停止。
- `schema/jpdb_r1_jockey_profile_v0_1_candidate.schema.json`: 厳格な許可field、direction=UNCLASSIFIED、prediction_safe=false。schema単独では全件identity/件数/日付の意味監査を代替しない。
- `tests/test_jpdb_r1_profile_builder.py`: 合成5テスト。KYI予定騎手とreference IDの区別、SHA/日付/重複/欠損/BAC頭数、ゼロ標本、同日・未来・期間外、A1/A2/A3・芝ダ・取消/中止/降着の境界。
- `src/jpdb_r1_real_profile_e2e.py`: 固定source用独立SUM(CASE...) SQL照合と再生成。個別馬プロファイルはprivate出力のみ。
- [実測集計証跡](evidence/jpdb_r1_real_profile_e2e_20261124.json): 個別馬・騎手の行は含まない。

## 2. 分析軸と利用範囲

対象: 固定2023-2025 Warehouseと2026-11-15まで97日PACI/SEDのJRA平地。v0.1 targetはこの2026 PACI manifest内の日付のみ。通常戦は15軸、新馬戦17軸、3暦年/365日/90日、race_date < D。各windowは2023-01-01でclip。ALL_FLAT、SURFACE、VENUE、VENUE_SURFACE、SURFACE_DISTANCE_EXACT、CLASS_GRADE_RAW、GOING_RAW、物理6軸を提供。通常戦はCLASS_ONLY/CLASS_SURFACE。新馬戦はNEWCOMER_ALL_FLAT/NEWCOMER_SURFACE/NEWCOMER_VENUE_SURFACE/NEWCOMER_SURFACE_DISTANCE_EXACT。GRADE空欄は不明として別CLASS_ONLY等の根拠を用いる。GOINGは対象BACから確定状態を取得できないためUNKNOWN、metrics=null。物理属性はBACと時点有効Course Masterで解決し、NULLは補完しない。物理P2集計の母集団はALL_FLAT、距離や芝ダと独立に加算しない。

元のP1候補母数と全件結果分類を保持。正常完走限定率と出走ベース候補率を混同しない。降着5・未知・不正完走の候補率は既存定義で非表示、REVIEW_REQUIRED。NO_HISTORYとTARGET_CONDITION_UNAVAILABLEを区別。30騎乗は既存の初期標本帯であり、能力や有意性を示すものではない。各証拠ID・redundancy_group_id・scopeを明示。P3市場・指数・能力残差・結果・予想印は出力しない。

### 新馬戦のソース認証

提供元の [BAC仕様4d](https://docs.google.com/document/d/1VAKG-fXd8sqvrXXbQvcTvmUxVCCjGH8eDLFTlxBtIiU/edit) の競走条件項目と [JRDBコード表](https://docs.google.com/document/d/19R1BkuhFE7yfwHH7WWx2Vqx5vMkiRaTiPIBK3FnWyS0/edit) のA1（新馬）、A2（未出走）、A3（未勝利）を使用。BAC/SEDの固定平地179,436行のclass/date/key一致を検査し、不一致0。A1は2023 302R/3,931行、2024 302R/3,982行、2025 304R/4,032行、2026 256R/3,269行。合計1,164R/15,214行（実出走母数とは別）。

## 3. 実行・実測

共通wheel-first C経路: registry承認済みprivate Drive ZIPのsize/SHA、bootstrapのGit blob SHA一致、隔離CPython3.13.5/Linux x86_64環境にDuckDB2.0.1/PyArrow25.0.1/NumPy2.2.4導入PASS。正本 `dependency_report()` 本体のblob SHA一致・status=success、完全なData Storage CLIはmaterializeせず直接関数を実行した。新規Actions起動なし。既存Readerのsource blob SHAを最新mainと比較。年次9本SHA一致、97組PACI/SEDバイト集合SHAは11/20 P3固定世代と一致。SED/BAC manifestは同一バイト集合から今回再生成した別serializationであり以前のmanifest SHA一致とは主張しない。

6/13と11/15の各3R（通常計2、新馬計4、芝・ダート双方）、76/76頭、3,672 Evidence、3,216数値セル/41,808件数・観測日独立照合PASS。同じReader・入力で2回生成したprofile bytes一致。2日分Schema PASS、対象結果・市場field・prediction_safe=trueの各注入拒否（6チェック）。合成5/5 PASS。厳密な歴史的配信時点は未認証。target_date当日と将来は履歴SQLから除外するが、固定source自体は回顧研究用。

## 4. R2に向けた母数所見

新馬4R・42頭の予定騎手について3暦年窓でn>=30かつ未解決結果なしのセルは、新馬全体41/42、同芝ダ36/42、同場芝ダ12/42、同芝ダ距離完全一致11/42。これはこの6レースでの小規模なcoverage診断であり一般化・能力の証明ではない。細かい条件を無理に優劣分類せず、広い条件への明示的な参照と比較の母数を保持する。R2では同騎手の同条件対非該当条件、同条件他騎手、時系列再現、馬質感度を事前固定し検証する。距離帯境界の候補は別契約として研究する。R2解釈規則・R3共通契約・R4 Shadow・R5 A/B・R6採否は未実装・未承認。

## 5. 再実行

既存の認証済みprivate sourceとSHAに結合する。`python src/jpdb_r1_profile_builder.py --help` / `python src/jpdb_r1_real_profile_e2e.py --help` が入口。歴史manifest、daily SED manifest、PACI manifestの期待SHAを渡し、profile builderは`--target-date`と`--race-key`を指定する。実行はC経路を優先、既存Actions-native要件は不変。実行時に最新mainのruntime registryを読み、固定の入力世代を無断更新しない。個別データ・private manifestはGitHubに掲載せずprivate runtime/Libraryで保持する。現行RaceNote、PWA、Confidence Z、Freeze、CURRENTは未変更。

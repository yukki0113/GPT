# RaceNote R3 — JPDB × BRDB 共通Evidence契約 v0.1 candidate (2026-11-24)

**FIXED SOURCE RESEARCH CONTRACT PASS / DUAL-SOURCE NEWCOMER E2E PENDING / NOT PRODUCTION AUTHORIZED**

上位正本は [JPDB×BRDB独立Evidence方針](racenote/RACENOTE_JPDB_BRDB_INDEPENDENT_EVIDENCE_POLICY_20261120.md)。JPDB R1/R2とBRDB M7の既受入出力を、同じ対象レース・全登録馬の独立研究sidecarへ投影する。統計の再集計・適性認定・順位付け・加点はしない。R3は技術契約であって予想改善の証明ではない。

## 1. 契約と実行

- `src/racenote_r3_independent_evidence.py`：private input manifestと期待SHAを必須化。受入receiptのprofile SHA、PACI SHA、BRDB M7 v0.3・④詳細・①②原出力SHAを照合。既存R1 `read_target_paci` を再利用し、BAC/KYIの全登録馬、race_key_raw×horse_no×horse_id、予定騎手、取消フラグ、対象日・条件を照合。馬名fallback禁止。欠落・重複・不一致・時点境界破りはfail closed。R1/R2の期間・evidence ID・condition・母数、①②原出力の観測値/母数/基準/区間を再照合する。BRDBの一部だけを渡すことは禁止。BRDBレース単位の未取得は全馬 `SOURCE_UNAVAILABLE` とする。
- 詳細：`schema/racenote_independent_evidence_v0_1_candidate.schema.json`。各根拠のfamily/scope/condition、元IDとsource asset、source/sample status、期間、母数・率・分母定義、比較対象、未解決感度、期間矛盾、as-of、redundancy groupを保持。R1/R2の各3窓全軸は数値・状態を保持し、詳細な異常分類等は元profileを参照。血統①②の別芝ダ/別距離帯も保持するが対象条件と区別する。
- 軽量：`schema/racenote_independent_evidence_preview_v0_1_candidate.schema.json`。1レース全馬を固定列定義付き行配列で返す。JPDBは3YのALL_FLAT、SURFACE、VENUE_SURFACE、SURFACE_DISTANCE_EXACT、対象新馬戦では追加4軸。ALL_FLATのpeer比較と各条件のrelative contrast・4群母数・短期窓の総合状態を表示。短期個別値、他比較、物理軸は詳細から参照。BRDBは父5scopeと母父の対象芝ダ全体・対象距離帯（元BRDBの帯定義を維持）。他芝ダ/他帯は詳細。選択は固定・数値大小非依存、重みや最良根拠の選定ではない。各行evidence ID、詳細SHAと省略/制限件数で逆参照可能。③④/D4数値は軽量版に含めない。
- `src/racenote_r3_independent_evidence_audit.py`：JSON Schema Draft 2020-12、独立した原出力照合と軽量行の逆参照を検証。private manifestを入力し、集計だけを監査出力へ保存する。`jsonschema` は監査用依存。新規10合成回帰は `tests/test_racenote_r3_independent_evidence.py`。

実行例（リポジトリroot、既存の適合venv、非公開scratch）：

```bash
PYTHONPATH=horse-racing/jrdb/src <approved-python> horse-racing/jrdb/src/racenote_r3_independent_evidence.py \
 --manifest <private-manifest.json> --manifest-sha256 <independently-pinned-sha> \
 --output <private-output.json> --preview-dir <private-preview-dir>
python horse-racing/jrdb/src/racenote_r3_independent_evidence_audit.py \
 --manifest <private-manifest.json> --manifest-sha256 <independently-pinned-sha> \
 --detail <private-output.json> --preview-dir <private-preview-dir> \
 --schema-dir horse-racing/jrdb/schema --output <aggregate-receipt.json>
```

入力manifestは `racenote-r3-private-input-manifest-v1`、assetsは `jpdb_r1`, `jpdb_r2`, `paci`, `jpdb_r1_receipt`, `jpdb_r2_receipt`、BRDB付は追加で `brdb_v03`, `brdb_relatives_detail`, `brdb_sire_bms`, `brdb_m7_receipt`, `brdb_detail_receipt`。各assetはpathとSHA256。manifest SHA自体は信頼済みの別経路から与え、改変manifestで自己認証しない。今回固定manifestはprivate archiveに保存。配置変更時は正本とreceiptのSHAを再照合し新manifestを作る。公開Gitへ個別profile、raw、private manifestを置かない。

## 2. 解釈・研究境界

- R1候補分母とR2解決済み分母、BRDB実出走分母は同義ではない。分母区別、4群母数、血統一意馬数・Wilson区間を維持。R2未解決感度範囲は信頼区間ではない。5pp/n>=30は記述表示基準に留まる。R2のCONTEXTUALは因果能力認定ではない。SUGGESTIVE・適性確定・confidence昇格を生成しない。
- JPDB歴史SED翌日可用は仮定、保存PACI版・血統歴史資料のstrict as-ofは未認証。BRDB年次同等性の研究受入は保持するが既存v0.3の時点状態を上書きしない。すべて `research_only=true`, `prediction_safe=false`, `production_authorized=false`。BRDB③④/D4は `restricted_refs` と原本SHAで保留状態・元根拠を参照、数値の暗黙利用を禁止。これは元データの破棄・不得意判定ではない。①②も観測値のみ、方向ラベルなし。
- `SHARED_JRDB_HISTORY_NOT_INDEPENDENT` を跨DBで共通設定、元の冗長性/overlapタグも詳細に保持。重複可能性を否定しない。各窓・父/母父・騎手等を独立票として足さない。市場・当日結果・払戻・スコア・印・予想順位を出力しない。現行v0.5.6 Reader/KYI allowlist、Gen0.3、Freeze、Confidence、BRDB CURRENT、Newspaper/PWAには接続・変更しない。

## 3. 固定実データ検証

R1/R2の2026-06-13・11-15固定成果物（通常2R/新馬4R、全76頭）を最新mainの受入receiptでSHA確認。BRDB M7の東京12Rは既存実PACI v0.3・④詳細・①②原出力の公開受入SHAと一致。**今回は既存受入出力の実データ結合と投影のE2Eであり、歴史Parquetからの再集計は実施していない。** 依存ソース・receiptのblobを最新mainと照合し、承認済みPython3.13.5/Linux x86_64 DuckDB2.0.1/PyArrow25.0.1/NumPy2.2.4 venvを再利用（共通dependency_report success）。C経路、新規Actionsなし。Schema監査はjsonschemaの別ローカル環境。

- 6R/76頭完全一致、両DB実データは通常1R/18頭（東京12R）、JPDBのみ5R/58頭。新馬4R/42頭はBRDB入力未取得、未検証。新馬戦の血統統計を他レースから流用しない。
- JPDB 3,672 evidence ID、数値セル3,216、比較9,192の原出力照合PASS。BRDB父90・母父180の計270観測を原①②とv0.3およびR3で一致確認。時点未認証の90 pairing、75近親関係、375近親条件観測（0走285）、66 D4を計606制限付き根拠参照に保存。未認証数値をReader数値欄に混入しない。
- 詳細2ファイル・軽量6ファイルSchema PASS、同一入力で2回生成し8/8 bytes一致、合成10/10 PASS。軽量598行、東京12R 198行/68,337 bytes（同レース詳細2,179,751 bytesに対し約3.1%）。全馬分は維持、詳細へのSHA/ID参照必須。
- [公開集計監査](evidence/racenote_r3_independent_evidence_20261124.json)。個別出力は非公開Library `/JPDB/R3/` に保存する。

## 4. 次工程

R3技術契約は固定sourceで受入。R4は既走馬と新馬戦を別にShadow評価する前に、同一PACI・同一全馬のBRDB出力を新馬戦で生成・受入し、R3結合を再検証する。BRDBの新馬特化母集団・時点状態・利用可能根拠はBRDB側の正式研究方針を尊重。必要な根拠の追加・保留解除は独立の受入に基づく。R3の成功をR4/R5、M6/M7本番、予想効果、Confidence Z変更の受入に読み替えない。

## 5. 新馬4R受入の実行準備 (2026-11-24)

[固定入力復元・受入実行器](RACENOTE_R3_NEWCOMER_REPLAY_PREPARATION_20261124.md) 参照。前回14ファイルSHA/76頭identity一致、4R42頭のplan実行PASS、複数レース別manifest実行器の合成8テストPASS。BRDB受入済み対象4Rの実入力は未取得のため追加両DB E2E 0R、R4未承認。新馬専用血統契約はBRDB B5と別途照合する。

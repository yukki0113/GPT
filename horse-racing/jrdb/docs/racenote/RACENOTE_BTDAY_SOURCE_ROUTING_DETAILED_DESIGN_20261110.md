# RaceNote BTDAY データソース自動選択・再抽選 詳細設計 v1.0

- 作成: 2026-11-10
- 状態: **設計確定案 / 実装未着手 / E2E未受入**
- 適用: v0.5.6のBTDAY T1及びPicker。Prediction/Confidence決定ロジックは変更しない。
- 上位方針: `RACENOTE_BTDAY_MULTIYEAR_SOURCE_AND_REPLAY_POLICY_20261110.md`
- 本書の「提案」は実装済み機能を意味しない。

## 1. 目的と非目的

### 目的
1. 抽選対象を「2025年Historical Warehouse固定」から、受入済み年次パックと日次PACIの全適格日に拡張する。
2. 年号をソース分岐条件としてハードコードせず、現行年/過去年の論理区分と実際のソース可用性を分ける。
3. 同一日付の繰り返し予想を許可し、各回を独立したBTDAY ID/immutable Freezeで管理する。
4. 既存の全頭比較LLM Prediction → Freeze → 独立Confidence → Freezeを再利用し、結果・オッズの予想側への混入を防ぐ。
5. 既存2025年経路・既存Freeze・過去selection履歴を壊さず移行する。

### 非目的
- PACI台帳を日次保存と完全同期させること（任意の定期/手動同期でよい）。
- 過去年の未整備Warehouseをこの改修だけで作成すること。
- 結果・配当の自動閲覧や検証成績の予想スレッドへの供給。
- 予想ロジック、Confidence A/B/C/Z、新聞/PWA工程の変更。
- 「2周目は失格」など周回数由来の予想禁止。

## 2. 現状（mainコード監査で確認した事実）

| 現行資産 | 実装状況 |
| --- | --- |
| `config/racenote_backtest_day_pool_2026.json` | 2025年Warehouseと2026年PACIを同居。2026-11-06最終更新、PACI最新登録日2026-11-01。source_mode/selection_cycle/used/selections有り。 |
| `src/racenote_backtest_day_picker.py` | 日付×source×cycle単位で抽選、usedと過去cycle証拠が抽選可否に影響。 |
| `src/racenote_v056_t1_orchestrator.py` | NEXTは2025年historical_warehouse専用。read_selectionも同条件。 |
| `.github/workflows/racenote_v056_btday_turn1_shared.yml` | 2025年BAC/KYIアーカイブを固定復元。PACIに非対応。 |
| `src/racenote_v056_forward_turn1.py` | 検証済み日次PACI→Reader生成済み。ただしDAILY専用root・DAILY ID・freshness gateを要求。 |
| `.github/workflows/racenote_v056_forward_paci_t1.yml` | 0～7日以内の開催前日付のみを受理。これをそのまま過去日のBTDAYへ流用しない。 |
| `.github/workflows/racenote_v056_llm_prediction_freeze.yml` / `...confidence_freeze.yml` | DAILY rootとBTDAY root双方を受理。 |
| 既存2025年Warehouse | 現行BTDAY経路で受入済み。2010～2024年の全期間が同経路で受入済みとはみなさない。 |

## 3. 用語と判定軸

- `target_date`: 抽選された開催日（ISO yyyy-mm-dd）。
- `operational_year`: 運用日JSTの年。**実行時の時計による論理ラベル**で、抽選ソースを自動確定するものではない。
- `calendar_bucket`: `CURRENT_YEAR` if year(target_date)==operational_year, else `PAST_YEAR` if earlier。未来日はBTDAY候補外。
- `source_mode`: 現に受入可能な資産種類。既存互換値 `paci` | `historical_warehouse` を継続。
- `source_generation_id`: immutable年次Warehouseの世代、またはPACI SHA+Drive IDに紐づく受入世代。
- `selection_cycle`: 非制御の履歴ラベル（移行後は抽選の必須filterではない）。
- `draw_occurrence`: 当該日付の非releasedな過去抽選件数+1。表示・監査用で抽選可否に使わない。
- `source_readiness`: `READY` / `PENDING` / `REJECTED`。T1実装・資料・検証証跡を含む。
- `prediction_blind`: 当該target日結果/配当/当日市場がT1 Readerと予想スレッドへ渡らない状態。履歴メタデータによる過去同日予想の存在は、結果露出とは別に監査。

## 4. データソースルーティング（重要）

**固定年号のif分岐は禁止。原則として、受入済みのソースを優先する。**

1. 日付が運用日JSTより未来、日付不正、JRA開催でない、又は除外フラグありなら候補外（従来の明示除外は維持）。
2. 対象年が過去年でも、当該日付を含む年次パックが未受入なら、既存の検証済み日次PACIを利用可能とする。暦年変わり目に自動切替/強制停止しない。
3. 当該日付の検証済み `historical_warehouse` が存在する場合はそれを優先し、それがない場合は検証済み `paci` を選ぶ。データソース選択は**抽選前**に日付ごと一意化し、同一開催日が二重に重みづけされないようにする。
4. 現行年は通常 `paci`、過去年は通常 `historical_warehouse` となる。ただし日付ごとの実ソース状態を正として扱う。
5. 受入済みソースがない日付は `PENDING` で抽選対象外。欠落を理由にJRDBから未承認の自動取得をしない。
6. ソース切替後も同日の旧Selection/Freezeが参照するsource id・SHAを差し替えない。新規BTDAYのみ切替後のソースを使用。

例:

| 実行日 | 対象日 | 受入状態 | 採用源 |
| --- | --- | --- | --- |
| 2026-11-10 | 2026-10-31 | PACI READY | PACI |
| 2026-11-10 | 2025-05-25 | Warehouse READY | Warehouse |
| 2027-01-03 | 2026-11-08 | 2026年Warehouse未受入、PACI READY | PACI |
| 2027-02-01 | 2026-11-08 | 2026年Warehouse READY、PACI READY | Warehouse |
| 2027-02-01 | 2024年任意日 | Warehouse未受入、PACIなし | 抽選対象外 |

## 5. 抽選テーブルv2（後方互換・破壊的更新回避）

### 5.1 インベントリと選択履歴の責務分離
- 既存 `days` / `selections` は**削除・リセットしない**。既存抽選番号/recordは不変。
- 新規 `source_inventory` （または別ファイル）を作成し、`target_date`, `source_mode`, `source_reference`, `source_generation_id`, `input_sha256`, `readiness_status`, `readiness_receipt_path`, `eligible`, `exclusion_reason` を持つ。PACIは `drive_file_id` を持つ。
- `selection_cycle` と旧 `used` は歴史的互換として読み込み、**新規v2抽選可否判定には使わない**。旧台帳の2周目行もsource/dateの候補へ正規化する。
- 現行の `historical_warehouse` の「2010～2025」固定バリデータは、受入済みgenerationのcovered yearsで検証する方式に変更する。
- 新規Selectionには `selection_schema_version`, `selection_id`, `target_date`, `selected_at`, `draw_seed`, `calendar_bucket`, `source_mode`, `source_generation_id`, `source_reference`, `source_receipt_sha256`, `draw_occurrence`, `selection_cycle_legacy`（任意）, `source_policy_version` を付与する。旧 `dates`, `sources`, `n` は継続して格納し、現行のReader/Freeze互換を維持。
- `selection_id` 採番は履歴末尾番号の単純推測ではなく、既存selections・ファイルパスと照合し衝突を拒否。既存4桁ID体系の上限に備えたID形式変更は、下流regex全面監査を別受入条件とする。

### 5.2 抽選アルゴリズム
```python
eligible_dates = distinct_dates(
    source_router.resolve(date)
    for date in inventoried_jra_dates
    if date <= operational_date and not explicit_exclusion(date)
    if source_router.resolve(date).status == "READY"
)
selected_date = uniform_random(eligible_dates, seed=cryptographic_seed)
source = source_router.resolve(selected_date)
reserve_immutable(selection_id, selected_date, source, source_receipt)
```
- 1日1抽選権。Warehouse/PACIの両在庫があっても同一日付は二重カウントしない。
- 過去の抽選回数は候補除外・重みづけに使わない（復元可能な同日反復を許容）。
- `eligible` / `exclusion_reason` は維持。**周回済みだけを理由とする排除**はしないが、既知の結果・市場が予想スレッドへ流入する危険のある個別日付は別途調査し、除外解除しない。
- 日付再利用では **必ず新しいBTDAY ID** を作り、過去のT1/Freezeはimmutableで保持。
- 乱数seed、候補集合digest、採用sourceのreceipt digestを保存し、同一候補集合で再現可能とする。
- `NEXT` は過去の未開始Selectionがある場合のみその同じSelectionを再開。再実行や同日重複は新規選定時だけ発生。

### 5.3 予約の原子性
- `READY` 判定は予約直前に行う。候補のPACI取得不能/世代不一致なら抽選候補から除外し再評価（無限再試行は禁止）。
- 複数リクエストは既存Actions concurrencyで直列化。最新mainを読み戻し、source receiptを固定してpool+selectionを同一commitへ。
- 既に予約・進行中のIDは別IDで再予約せずresumeする。失敗時は同一IDで原因修正・再試行。中断記録とreleaseは監査可能とし、過去履歴を消さない。
- 本番の抽選だけでT1の外部取得を全面事前実行しない。事前の `READY` はソース正本/公開状態/固定digest/runner対応の受入証拠で判定し、取得後の不一致はfail-closedで停止、同一IDから復旧する。

## 6. T1処理契約と責務

### 6.1 共通入口（新設するadaptor）
- `src/racenote_v056_btday_source_router.py`: 日付からソース選定、readiness判定・受入証拠検証。**結果/配当APIなし**。
- `src/racenote_v056_btday_paci_t1.py`: PACIによるBTDAY正規RootのT1。既存 `racenote_v053_from_paci.py --prep-only`, `racenote_v054_kyi_bundle`, `racenote_v056_single_day.init_session`, `racenote_v056_authoring_bundle` を再利用。FORWARD共通ビルダーを抽出して利用することが望ましい。
- `src/racenote_v056_t1_orchestrator.py`: 日付抽選・selection source固定・T1呼び分け。データ変換やLLM判断は実装しない。
- `.github/workflows/racenote_v056_btday_turn1_shared.yml`: source_modeでprepare jobを分岐。既存Warehouse経路は保全し、PACI用prepareを追加。二重同時実行を防ぐ。

### 6.2 Historical Warehouse経路
- 既存の固定SHA/manifest検証済みのWarehouse材料で、当該日付をas-of-exclusiveとして再構築。
- 年次パックを増やす場合は年ごとに受入済みsource_generationと抽出可能coverageを宣言。2025年BAC/KYIを2026年や未対応年へ流用しない。
- 各レースReaderの過去走日付は `< target_date` を検査。出走馬/レース構成の対象日再現性をチェック。

### 6.3 日次PACI経路（2026年など）
- 既存Drive/PACIフォルダ正本にある `PACIyyMMdd.zip` を確定し、parent・ファイルID・日付一致・ZIP CRC・KYI内容・SHA-256を検証。
- Actionsが認証付きDriveを直接操作しない。**公開・事前承認・SHA固定済みのread-only transport**だけを既存共通helperで取得するか、適法な事前ステージング済みArtifactを利用。Drive非公開かつ承認済み搬送が無い場合は `PENDING` として抽選不可。現行FORWARDのgdown直呼出をBTDAYへ無条件に複製しない。
- `racenote_v056_forward_turn1.py` は `daily/YYYYMMDD/v056_day` と `DAILY-YYYYMMDD` を要求するため、そのままBTDAYへ呼び出さない。共通の材料変換部を分離して、BTDAY root `backtests/BTDAY-NNNN/YYYYMMDD`、Selection ID `BTDAY-NNNN` に渡す。
- FORWARDの「今日から7日以内」制限はFORWARDの開催前入口に残し、BTDAYには適用しない。BTDAYは過去日付の源証拠とas-of判定を要求する。
- Analysis/RRDB/RaceLapは**対象日以前の時点の証拠のみ**を用いる。FORWARD用A05 freshness gateを過去日にそのまま適用せず、過去日as-of-exclusiveの入力世代/カットオフ/禁止フィールド検査をBTDAY用に設ける。現行CURRENTを過去日の結果入りで参照してはならない。
- 対象日のPACIにない結果や配当を補完しない。Reader生成後、対象日市場・配当・結果フィールドの不存在を検証する。

### 6.4 共通出力
```
horse-racing/jrdb/backtests/BTDAY-NNNN/YYYYMMDD/
  operation_handoff.json
  source_audit/selection_source_receipt.json
  day_prep/
  forecast_prep/
  v054_inputs/kyi_bundle.json
  v056/session.json
  v056/reader_manifest.json
  v056/reader/*.json
  v056/authoring_bundle/
  # T2提出後のみ:
  v056/incoming/llm_decisions.json
  v056/frozen/
  v056/incoming/llm_confidence.json
  v056/confidence_frozen/
  v056/turn2_summary.json
```
- `operation_handoff` に `source_mode`, `source_generation_id`, `source_sha256`, `source_receipt_sha256`, `as_of_exclusive`, `market_blind=true`, `target_market_opened=false`, `result_opened=false` を明示。
- Selection ID/date、Reader/Session/authoring件数、全馬番・レース、入力ファイルSHA、Reader manifest SHAを読み戻して整合検査。
- 1R ZIPの配布処理 `racenote_v056_racezip_delivery.py` はこの共通出力に対して実行。sourceの違いでZIP形式を変えない。

## 7. T2以降と評価の分離

- LLMは当該BTDAYのReaderだけを使って全馬比較しPredictionを著述。Prediction Freezeがmainで成功した後、凍結済み◎だけを対象に別途Confidenceを著述してFreeze。
- `v056/turn2_summary.json` の `TURN2_COMPLETE`、双方のFreeze/SHA・run SUCCESSで完了判定。
- 予想スレッドには結果や配当、成績の評価ファイルを渡さない。結果/回収率算出は別実行主体・別許可パスで行う（秘密保持の実装はReader allowlistとツールアクセス境界を別途テスト）。
- 同じ日を複数回予想することは認める。過去の同日結果を**入力として渡さない**ことを必須条件とする。
- 検証成績の評価側では `draw_occurrence` 等を監査用に保持するが、初回と再利用の集計を機械的に強制分割しない。必要に応じ評価側で区分比較できるようにする。
- モデル内部に過去同日の経験がある可能性はスレッド分離だけで数学的に消去できないため、`result_not_exposed_via_inputs` と `independent_first_seen` は同義にしない。いずれも予想の禁止理由ではない。

## 8. 状態遷移・エラー設計

```
INVENTORY_READY
  → SOURCE_RESOLVED
  → RESERVED (selection.json immutable)
  → T1_RUNNING
  → READY_FOR_V056_AUTHORING
  → PREDICTION_FROZEN_CLEAN_BLIND
  → CONFIDENCE_FROZEN_CLEAN_BLIND
  → TURN2_COMPLETE
```

- `SOURCE_UNAVAILABLE`: 予約前なら候補から除外。予約後なら停止して同じIDを再試行し、黙って別日へ抽選し直さない。
- `SOURCE_SHA_MISMATCH` / `FUTURE_INFO_DETECTED`: fail-closed。Reader/Freeze作成禁止。入力世代やtransportを監査。
- `PARTIAL_T1`: immutable rootを上書きしない。既存T1と整合する一時生成物からの安全なresume、または運用管理者による取消記録・新IDでの再選定を行う。
- `SELECTION_CONFLICT`: main競合時は最新ファイルとselectionを読み直し、forceせず再試行。
- `ALREADY_READY`: 同一Selectionの再起動では既存T1を検証して返し、別のT1を作らない。
- 識別子とsourceの整合性が確認できなければすべて停止し、旧Freezeを改変しない。

## 9. 変更対象（実装順）

| 優先 | ファイル/機能 | 変更 |
| --- | --- | --- |
| P0 | `src/racenote_v056_btday_source_router.py`（新規） | 日付単位source解決、READY証拠、年切替、重複source排除 |
| P0 | `src/racenote_backtest_day_picker.py` | v2のdate単位均等抽選、過去cycle/used非制御、採番衝突保護 |
| P0 | `src/racenote_v056_t1_orchestrator.py` | 2025年固定排除、source別T1入口、旧Selection互換 |
| P0 | `src/racenote_v056_btday_paci_t1.py`（新規） | PACIをBTDAY rootへ正規化、as-of検査、既存T1部品再利用 |
| P0 | `.github/workflows/racenote_v056_btday_turn1_shared.yml` | sourceに応じた材料取得/T1分岐、履歴の固定、Artifact同一契約 |
| P0 | `config/racenote_backtest_day_pool_2026.json` | 過去履歴を保持しつつsource readiness情報を移行（名前の改名は別判断） |
| P1 | `tests` 群 | picker、router、T1、Freezeの回帰・例外テスト |
| P1 | `docs/racenote/RACENOTE_V056_BTDAY_PREDICTION_THREAD_HANDOFF_20261030.md` | 旧2025年限定説明を新経路の受入後に更新 |
| 不変 | Prediction/Confidence workflow | 既存BTDAY root受入のまま。必要な追加検証のみ |

## 10. 必須受入テスト

1. 2026年のPACIを抽選しBTDAY rootへT1が完成、Reader/Session/選択元SHA一致、ZIP公開。
2. 2025年Historical Warehouseを抽選し、現行T1相当の全レースが再現。
3. 年跨ぎ: 2027-01-01の2026年候補はWarehouse未受入ならPACI、受入後はWarehouseになる。
4. 同一日付を連続2回抽選（候補集合1日の固定seed）して別BTDAY ID/immutable Freezeへ進める。
5. 候補日同一のWarehouse+PACI重複登録でも抽選確率が倍にならない。
6. 旧履歴181件と既存Freeze・2025年T1を一切書き換えない。
7. 旧used=true/cycle2のみの候補も過去履歴で排除されず抽選できる。
8. 未受入年次パックや非公開PACIは候補外。抽選後SHA不一致は同ID停止。
9. Readerから対象日結果/配当/当日市場/対象日以後の情報が排除される。
10. Prediction→Confidence二段階Freezeの双方がSUCCESS、main読み戻し、結果非参照。
11. `NEXT` / `EXISTING` / `STATUS` / `T2_ONLY` の冪等性、再入、競合の回帰。
12. 2027・2028年へ進んでも年号のコード変更なく年次切替される（入力世代受入は別途）。
13. 既存FORWARDの7日ガード、DAILY root/ID不変。
14. T1未対応日が引かれて予約済みだけになる状態を防ぐ。

## 11. 段階導入・切戻し

- Phase A: source router、在庫v2、契約とオフラインテストを追加（旧v056 NEXTはまだ変更しない）。
- Phase B: PACI用BTDAY T1をshadow/検証モードで受入。既存2025年経路と双方に同じT1出力契約を検証。
- Phase C: 2025/PACIの双方がE2E PASSとなったら新source routerでのNEXTを有効化。旧2025年固定経路を切戻し用に保持。
- Phase D: 周回数が予想可否に影響しないことと、成績/結果の予想側非参照を監査。
- 切戻しは「新規mixed-source NEXTを停止し旧2025年T1へ戻す」。過去のSelection、Root、Freezeには触れない。

## 12. 実装前の要確認事項

- 現行FORWARD PACIのDrive搬送コードは `gdown` を呼ぶ箇所があるため、`.gpt/GITHUB_OPERATION_POLICY.md` の公開・SHA固定helper制約との整合を実装時に監査する。
- 既存2026年PACIのどの日付に完全な事前時点Analysis/RRDB/RaceLapが利用できるかは、本書時点では全日確認していない。READYを宣言する前に証跡検証が必要。
- 年次Warehouseの2010～2024と将来2026年以降の使用可能年次は、manifest・coverage・T1実測受入の確認後に段階開放する。
- v2のdate単位抽選と旧Selection/poolの互換、同時実行を含む移行をテストする前に本番抽選を切り替えない。

# Codex実装依頼：JRDB特化予想Reader / Orchestrator v1（全工程一括）

Status: READY_FOR_CODEX
Target repository: `yukki0113/GPT`
Implementation root: `horse-racing/jrdb/forecast_reader/`
Owner issue: この指示書を参照する実装Issue
目的: レース日・競馬場・レース番号を指定するだけで、**過去10暦年・同名同条件優先・4開催以下なら近似条件検索・8軸統計・当日PACI全馬前走詳細・監査**を一括生成する決定論的Readerを実装する。

## 0. 必読正本・実装境界

実装前に最新mainと関連open PRを点検し、次の実在コードと契約を必ず読む。コードがGitにないことを理由にRawをWeb検索しない。

- `horse-racing/jrdb/forecast_protocol/README.md`
- `horse-racing/jrdb/forecast_protocol/FORECAST_POLICY.md`（最上位の**ユーザー確定予想方針**）
- `horse-racing/jrdb/forecast_protocol/FORECAST_PROCEDURE.md`（as-of・結果遮断・ゲート）
- `horse-racing/jrdb/forecast_protocol/TEACHER_EVIDENCE.md`（人手予想の例への参照）
- `horse-racing/jrdb/README.md`、`src/jrdb_raw.py`、`src/jrdb_raw_history.py`
- `horse-racing/jrdb/schema/jrdb_analysis_schema_v1_4.sql`
- `horse-racing/jrdb/docs/reference/JRDB_File_Relation_Key_Definition.md`
- `horse-racing/jrdb/docs/JRDB_Analysis_Warehouse_Input_Contract_v1.md`
- `horse-racing/jrdb/src/racenote_history_engine.py`、`src/racenote_history_enrichment.py`（再利用可能な関数・事前データ境界のみ参照）
- `tools/data-storage/README.md`、`tools/data-storage/docs/DYNAMIC_DRIVE_MANIFEST_RUNBOOK.md`
- `tools/codex-cloud/README.md`

**最重要原則：** Readerはデータの観測・検索・比較・監査まで。◎○▲△、勝率推定、買い目、結果照合は**作らない**。既存RaceNote Gen0予想ロジック、Analysis v1.4 schema、本番PWA、共通Raw Readerの固定長仕様を勝手に変更しない。新規byte-offset、専用DuckDBエンジン、Web/Drive API clientの複製禁止。明示的な契約変更を要する場合、理由を報告して既存正本を守る。

## 1. 提出物とdirectory

```
horse-racing/jrdb/forecast_reader/
  README.md
  docs/
    FORECAST_EVIDENCE_CONTRACT_v1.md
    IMPLEMENTATION_REPORT.md
  config/
    sampling_rules_v1.json
    race_name_aliases_v1.json
    jrdb_class_normalization_v1.json
  forecast_reader_runner.py
  src/
    forecast_orchestrator.py
    input_source_resolver.py
    race_condition_resolver.py
    exact_sampler.py
    similarity_sampler.py
    trend_aggregator.py
    previous_run_reader.py
    runner_evidence_joiner.py
    contract_validator.py
  tests/
    test_exact_sampler.py
    test_similarity_sampler.py
    test_asof_guard.py
    test_previous_run_reader.py
    test_forecast_bundle_contract.py
    test_integration.py
    fixtures/
```

ファイル名は軽微な統廃合可だが、責務と単一CLI入口を維持。JSON configは既存依存がない場合の標準形式（設計上のYAML提案から合理的に変更可）。外部オーケストレーション（GPT/native Drive connector→ファイルSHA pin→必要ならActions fallback→結果取得）と、内側の純粋・決定論的Reader状態機械を明確に分ける。

## 2. 外部CLI / request contract

単一入口（新規作成）：

```bash
python horse-racing/jrdb/forecast_reader/forecast_reader_runner.py --request request.json --plan --output-dir OUTPUT
python horse-racing/jrdb/forecast_reader/forecast_reader_runner.py --request request.json --run --inputs inputs_manifest.json --output-dir OUTPUT
```

要求例（schema version厳格検証）：

```json
{
  "schema_version": "forecast-reader-request.v1",
  "protocol": "human_statistics_v1",
  "target": {"date":"2026-10-25","venue":"京都","race_no":11},
  "as_of":"2026-10-25T15:30:00+09:00",
  "history_years":10,
  "mode":"historical_backtest",
  "detail":{"previous_runs":1}
}
```

- `--plan` はアクセス不要の決定論的取得計画を返す。PACI日次ファイル、Analysis canonical、追加Rawが必要になる場合のsource requestを正規化。file IDは動的に解決、日次固定値をGitへ埋め込まない。
- `--run` は指定ローカル入力を検証する。各sourceのactual SHA256、size、file name、source kind、対象日・版を監査し、合わなければ fail-closed。
- 必須入力がない場合は構造化`NEED_INPUT`と取得計画を出し、外側がDrive connectorで補い**同一request**から再実行できること。自前Google Drive認証・Web代替検索は禁止。
- 予想対象レース条件は原則PACI BACで決定。ユーザー指定の名称/距離等は任意assertionとし不一致をエラーにする。
- `as_of` はtimezone必須で、当日レースの発走後に置かない。日時が不確実な前走は`race_date < target.date`でfail-safe。開催済みか否かで実行を中止しない。
- `mode=pre_race` / `historical_backtest`は同一の結果遮断規則。対象レースの結果・払戻・最終人気を**読み出す経路を作らない**。
- 既存`tools/data-storage`のdynamic manifest・`[DATA_STORAGE_FALLBACK]`経路をCLIオーケストレーションと接続。Actionsに任意shellを導入しない。既存entrypoint制約に適合する実行方法を用意し、統合手順をREADMEへ記載する。

## 3. オーケストレータの状態機械

```
INIT
 -> SOURCE_READY
 -> TARGET_RESOLVED
 -> EXACT_SELECTED (S0)
 -> BRANCH_SELECTED (S0>=5なら終了/<=4なら補完)
 -> SUPPLEMENT_SELECTED (必要時のみS1..S3)
 -> TREND_READY (8軸必須)
 -> RUNS_READY (PACI KYI->ZED優先)
 -> MATCH_READY (全馬の一致/不一致/不明)
 -> CONTRACT_VALIDATED
 -> PUBLISHED (JSON + audits)
```

各状態は入力・成果物・status・failure codeを明示し、途中で印や買い目を生成しない。ゲートA/B/Cに対応し、要件欠落時はPASSしない。JSONはソート・型・null等を決定論化し、同一入力SHA+code versionで再現可能にする。

## 4. Sample Selector：S0 完全一致

- 期間：**予想対象年の前年まで10暦年**。2026年予想は2016–2025年。対象レース自身の結果は禁輸。
- 特別競走は**同名かつ同条件**。名称は空白・全角半角等の無害な正規化のみ。レース名の変更は根拠付き明示aliasのみ。
- 同条件は**競馬場・芝/ダ・距離・クラス/格付・性齢/牝限などの施行資格**を最優先して照合。コース内外/回り・重量条件・時期・開催替えも可能な範囲で確認。単に`grade_code`だけで「3勝クラス」と判定しない。JRDB code mapと実スキーマの意味を検証、未知値を黙って一致扱いしない。
- `race_key`単位のユニークな**開催数**で4/5件の閾値を判定。出走馬延べ頭数ではない。
- `S0>=5`: S0のみ採用しfallback=false。`S0<=4`: S0件数を記録し補完探索。名称は同じでも阪神移設の菊花賞は京都S0へ混ぜない。
- S0が0でもSOURCE欠落と混同せず、正当な0件と欠損/UNKNOWNを監査で区別。

## 5. 類似サンプルの自動分岐 S1-S3

**以下の細則は実装用の提案値であり、FORECAST_POLICYの確定事項ではない。** config化し、テストで再現性を保証。条件を緩めて母数を作ることを目標にしない。

| stage | 維持 | 一部緩和 |
|---|---|---|
| S1 | 同場・芝ダ・距離・クラス・性齢/牝限・コース形態・重量条件 | 名称不問、開催時期±21日 |
| S2 | S1と同じ | 開催時期±42日 |
| S3 | 同場・芝ダ・距離・クラス・性齢/牝限 | 開催時期±70日、コース細部/重量条件の一部 |
| STOP | 場・芝ダ・距離・クラスを不変とする | 他場・別距離・別クラスは自動採用禁止 |

- S1の適格候補が見つかればS2以降は実行しない。S1候補が1件でもあれば追加母数目的で下位へ進まない。
- 10暦年内、S0との重複なし。同一年の近似候補から代表1レースを選ぶ方式はconfigの提案defaultとし、年内複数採用もモード別に試験して報告。tie-breakは一致度→季節的日差→race_keyの順。年跨ぎ/うるう年の季節差を正しく計算。
- 主軸の統計は`exact_only`。補完`supplement_only`を独立提示、`combined_descriptive`があっても混ぜたことを明示。S0の小標本を自動減点しない。
- 絞り込みの根拠、S1/S2/S3探索結果、採用・除外レース、condition mismatchを`sampling_audit.json`へ出す。
- 不確定なJRDBコードの旧/新クラス対応は公式定義で確認し、根拠付きdate-effective mappingを追加。未解決ならUNKNOWN。適当に1600万下と3勝クラスを同一化しない。

## 6. Trend Reader：8軸・過去10年

過去開催S0（必要時は別枠でS1..S3）から次の全8軸を生成する。
`人気、枠順、脚質、馬齢、血統（種牡馬/母父）、騎手、前走距離、前走クラス`。
出力はgroup/starts/(1着,2着,3着,着外)/top3/missing_count/元コード/対象race_keys。特殊な項目は比較不能の理由を返す。
- 過去レースの最終人気・着順は**前年までの歴史統計に限り使用可能**。
- 直近前走の距離/クラスはAnalysisの`prev_result_key_1`、`prev_race_key_1`を起点に`(prev_race_key_1,horse_id)`で過去行へLEFT JOIN（前走日 < 当該出走日、unique監査）。前走行検索は2016年レースの2015年以前へ遡ってよいが、2015年開催を集計母集団へ追加しない。
- Analysis Liteで取れない列は受入済みWarehouse `sed/bac` やSED/Rawへ段階的に照会。ただし実列スキーマを確認し、取得できなければ`missing_count`を返す。推測しない。
- 人気や騎手の8例の偏りを「小標本だから」という理由だけで割り引かない。母数/coverageの記録を保ち、レース固有の傾向をそのまま証拠として返す。

## 7. 全馬 前走Reader

優先順位：
1. **当日PACI内KYI→ZED**（KYI`previous[0].result_key` = ZED `result_key`）。固定長は共通`jrdb_raw.py`の`Parser`を再利用。`ZED=SED layout`。
2. キー未一致・欠損時、既存`jrdb_raw_history.get_horses_runs(..., before=target.date)`によるSED batch lookup、または必要な列・キーが確認済みのWarehouseから補完。欠損・追加材料が未取得なら`NEED_INPUT`/coverageを返す。
3. Web fallbackなし。対象レースの結果Rawを開かない。

正規化項目：horse_id, race_horse_key, prev_result_key, prev_race_key, prev_date, prev_name, prev_venue, prev_distance, prev_class, prev_grade, prev_finish, prev_popularity, prev_field_size, prev_corners (1-4角、非施行/null区別), prev_abnormal, source kind/SHA。必要時5走へ拡張可能に設計するがv1は**前走1走を必須**。
- 競走成績キーは`blood_registration_no+YYYYMMDD`（result_key）。同名馬や曖昧名で結合しない。
- 同一キー重複/当日以降の結果/不一致をAUDIT。通過順位`corners`と`running_style`は別項目のまま保存し、Readerで印を調整しない。
- `PACI261025.zip`（JRDB Drive正本）京都11Rを回帰実データに使い、**18/18 KYI→ZED**、⑧ロブチェン [5,7,8,4]、⑬キンググローリー [1,1,1,1]、⑮シートゥサミット [10,8,1,1]を検査する。ユーザーの実データが使えない場合は事実を模したfixtureを使用し、「実データ確認は未完」と明記する。
- 0 cornerや未施行の解釈は公式仕様と照合。走行実態はそのまま提示し、静的脚質分類を通過順の代わりにしない。

## 8. Evidence Bundle・監査・エラー契約

出力（機械判読JSON）：
```
OUTPUT/<request_id>/
  forecast_evidence.json
  sampling_audit.json
  source_audit.json
  manifest.json
```
`forecast_evidence.json`の必須骨格：
```json
{
  "schema_version":"forecast-evidence.v1",
  "status":"PASS",
  "target":{"date":"2026-10-25","venue_code":"08","race_no":11,"race_name":"菊花賞","surface":"turf","distance_m":3000},
  "policy":{"version":"human_statistics_v1","years_from":2016,"years_to":2025},
  "sampling":{"exact_count":8,"fallback_triggered":false,"selected_stage":null,"supplement_count":0,"exact_race_keys":[],"supplement_race_keys":[]},
  "trends":{"exact_only":{"popularity":[],"frame":[],"running_style":[],"age":[],"sire":[],"jockey":[],"previous_distance":[],"previous_class":[]},"supplement_only":null},
  "runners":[{"horse_no":8,"horse_name":"ロブチェン","running_style_code":"2","previous_run":{"source_kind":"PACI_ZED","corners":[5,7,8,4]},"trend_matches":[{"dimension":"running_style","result":"mismatch"}],"data_coverage":{"previous_run":"available"}}],
  "gate_status":{"A":"PASS","B":"PASS","C":"PASS"},
  "provenance":{"input_artifacts":[]}
}
```
これは**骨格サンプル**であり、実例の配列を省略したままPASSにしてはいけない。実際の出力は全馬・全8軸・欠損理由を持つ。対象結果/払戻/最終人気/今走finishが入らないことをJSON schemaとテストで強制。
- `sampling_audit`: 候補一覧、同名同条件の判定、各近似Stage/採否/理由/SQLとparameters、unique race count。
- `source_audit`: source SHA/bytes/schema/version、PACI・Analysis coverage、as-of証跡、全馬前走結合率、data leak guard。
- `manifest`: request hash、reader version、生成物hash、入力SHA、再生成のためのコードSHA。atomic output。
- failure codes：`INVALID_REQUEST`, `SOURCE_NOT_FOUND`, `SOURCE_AMBIGUOUS`, `SOURCE_CHANGED`, `HASH_MISMATCH`, `UNKNOWN_CLASS`, `UNKNOWN_CONDITION`, `NO_ACCEPTABLE_SUPPLEMENT`, `MISSING_PREVIOUS_RUN`, `FUTURE_LEAK`, `DUPLICATE_RACE_OR_RUN`, `INCOMPLETE_8_AXES`, `UNVERIFIED_AS_OF`。
- `PASS/PARTIAL/BLOCKED/NEED_INPUT`を明確にし、欠損や時点不明で**未検証のままPASS禁止**。8軸比較不可なら理由付け、母数が少ないだけなら減点/停止しない。

## 9. 結果漏洩防止・バックテストの受入条件

- 過去開催の結果は歴史の`exact/supplement`にのみ許可。予想対象の結果SED/HJC・払戻・今走最終人気への参照経路を作らず、Webによる結果検索を行わない。
- `as_of_exclusive=target.date`を前走/履歴JOINに強制。対象当日を既に終えたからと処理中断しない。sourceが後日更新なら当時のsnapshotであったかをprovenanceへ記録、保証できない場合`UNVERIFIED_AS_OF`。
- Readerの後に別フェーズで予想freeze→その後Result Query/Evalへ渡す。Readerはresult queryを直接呼ばない。
- 漏洩禁止をmock/monkeypatch、出力フィールド検査で負例テストする。

## 10. 最低テストマトリクスと完了判定

T1 条件：京都芝3000m菊花賞の2016–2025のS0は京都8/阪神2除外、fallback=false。名称同じ条件違いはS0除外。race_key文字列保持。
T2 分岐：S0=5→no fallback、S0=4→fallback、S0=2→S1、S1空→S2、S1非空→S2禁止、S3空→NO_ACCEPTABLE_SUPPLEMENT。日付±21/42/70、年跨ぎ、うるう年、同一年代表、duplicate除外、理由監査。
T3 統計：8軸全完了。正規化クラス検査。2016年の前走2015年を取得しても集計対象には含まれない。exact/supplement集計を分ける。着別度数一致、欠損数。
T4 前走：PACI京都11R KYI 18/18→ZED、上記3頭のcorners、欠損/重複/未来/0-null処理。
T5 I/F：--plan→connector materialize（運用手順）→SHA pin→--run→4JSON。NEED_INPUT追加後同request再実行。既存data-storage Actions fallbackが実行可能で監査を取得できる。
T6 事例：G1、3勝クラス名称/施行条件変更、完全一致0件、全データ同じでcanonical output hash一致。No Web/no target results regression。既存JRDB/Raw/Data Storage関連テストのリグレッション。

- 新規CI workflow、または適切な既存checksへテスト追加。
- 所要の外部データが取得できないときはmock fixtureでできる部分を最後まで実装/検証し、リアルデータ未実施をREPORTへ記録。未検証をPASSと偽装しない。
- CIが失敗した場合は原因修正・再実行を可能な限り実施。停止/permission blockerは明示。
- 変更コード、テスト、README、JSON contract、実装結果レポートを**ひとつのPR**にまとめる（タスク分割は内部で可）。
- `forecast_protocol/` の予想原文は修正しない。変更提案はREPORTに記述し、既存資産を破壊しない。
- `docs/IMPLEMENTATION_REPORT.md` にstatus、変更一覧、branch/commit/PR、実行コマンド、テスト/CI結果、データ実測・coverage、未解決・関連open PRを記載。

## 11. Codex Cloud 実行規則

- published GPT Cloud Environment。まずmain及び関連open PRの現況をbuilt-in GitHub connectorで確認。古いworkspaceで指示書がない場合はshell git fetch/pullで解消しない。mainにある指示書を参照できる新しいタスクとして始める。
- 作業はまとめて継続し、可能な修正と検証を同一タスク内で完結。一般的な設計相談だけで終えず**実コードとテストを作る**。
- GitHub書込はbuilt-in GitHub connector（branch/commit/PR）を用い、shell `git add/commit/push/fetch/pull`に依存しない。
- Drive正本の探索と取得はconnected native Google Drive connector。大容量原本・ZIP・ParquetをGitのPR/Issueへ貼らない。Secrets新規設定不要。
- 作業終了後はPR URLとREPORTをIssueで通知する。**明示依頼なくmainにはmergeしない**。必要な未解決依存・保留PRをreportに列挙。

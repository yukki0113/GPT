# Boat racing GPT workflow

Updated: 2026-09-13

## 1. 開始時の確認

新しいChat / Workスレッド、または会話量上限による引越し後は、過去会話の要約だけを前提にせず latest `main` を確認し、原則として次を読む。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. `boat-racing/.gpt/HANDOFF.md`
4. 本 `WORKFLOW.md`
5. 対象工程の `docs/` / `src/`
6. D. Actions-Native Executionを使う場合だけ対象 `.github/workflows/`

司令室・会場選別・仕様改訂研究では、さらに `docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md` を読む。

日次の最新対象日、累計成績、記帳済み最終日、直近run ID等は本書へ固定せず、Google Drive / Google Sheets / GitHub Actionsの各正本から再取得する。

## 2. GitHub作業の経路選択

GitHubを使う作業は開始時に次の4系統へ分類する。

- **A. Read / Audit**
  - repository / file / commit / issue / workflow / artifact / SHA / run状態の確認。
  - Issue不要。
- **B. Git Change**
  - source / test / docs / config / workflow等のUTF-8テキスト変更。
  - latest main、path存在、現内容を確認してdirect create/update/deleteする。
  - Git変更だけを目的としたIssueは作らない。
- **C. Pure Deterministic Execution**
  - Git正本moduleと必要入力をChat側で取得でき、secret・特殊runner・Actions監査証跡が不要な処理。
  - CSV/JSON整形、join、集計、scoring、SHA、差分、artifact回収後の検証等は原則C。
- **D. Actions-Native Execution**
  - Secrets、認証付き外部取得、Actions artifact chain、長時間・大容量、runner依存、immutable freeze、監査run、またはChatローカルで正本moduleを同一条件実行できない処理。
  - fully validated requestをIssueで1回だけ起動する。

「GitHubにmoduleがある」ことだけを理由にDを選ばない。

### 現行D経路

BOAT RACE公式取得をChatローカルで正本fetcherと同一条件再現できない場合は、次を使用できる。

- 出走表取得: `.github/workflows/boatrace_racelist_issue.yml`
- 直前情報取得: `.github/workflows/boatrace_pre_race_issue.yml`
- 結果取得・予想照合: `.github/workflows/boatrace_results_chat.yml`

manual workflowは人手補助経路として扱う。

**台帳記帳はD経路ではない。** Googleサービスアカウントおよび台帳記帳用Issue / Actions経路は廃止済みであり、起動しない。

### Issue preflight / retry

Dを使用する場合は、ルート `.gpt/README.md`、`.gpt/ISSUE_REQUEST_CONTRACTS.md`、対象workflow/parser、競艇固有docsをIssue作成前に確認する。

- title / request_id / JSON parse / 必須キー / 値域 / upstream実値を事前検証する。
- Issueを先に作り、不足項目を後から補わない。
- `status=partial` / `failure` を成功扱いしない。
- retryはRESULT / artifact / failed stepを確認し、原因分類後に行う。
- `REQUEST_INVALID` は本文を修正する。
- `DOMAIN_VALIDATION_FAILED` は正常なfail-closedとして同一入力を盲目的に再実行しない。
- implementation / permission / concurrency問題はrequest再送だけで解決しない。
- 新requestでは旧run ID / artifact名を使い回さない。

## 3. 正本

### GitHub

Python、tests、README、予想仕様、運用文書、workflowは `yukki0113/GPT` `main` を正本とする。

### Google Drive data

Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`

日次原本:

- `racecards`
- `predictions`
- `prediction-rationales`
- `sales-selection`
- `results`

日次成果物、ログ、HTMLキャッシュをGitへcommitしない。

### Google Drive analysis

Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`

バックテスト、結果参照前固定、比較資料、仕様改訂判断を保存する。

### Google Sheets ledger

ネイティブGoogleスプレッドシート `競艇note販売運用台帳` を継続台帳の正本とする。

- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- timezone: `Asia/Tokyo`

Drive旧Excel版およびGitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットであり、通常運用へフォールバックしない。

## 4. 2026-09-01以降のForwardTrial

現行Controlは `ForwardTrial_Ver0.1`。

開始時に読む仕様:

1. `docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
2. `docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

前者を優先し、後者は基礎・履歴仕様とする。

### 情報遮断

事前予想・販売選別のfreeze前に、当該日の以下を参照しない。

- results
- 確定着順 / 払戻 / オッズ
- 展示 / 直前気象
- 外部予想 / SNS
- 結果を示唆する検索結果・結果台帳

結果参照後にA/B/C、軸、相手、買い目、販売Score、販売順位、掲載区分を再生成・変更しない。

### 日次予想

公式出走表CSVを取得済みなら、予想はCとして `src/forward_trial_predict.py` を使用する。Chat内に別ロジックを再実装しない。

結果参照前に同一freezeで次の3CSVを固定する。

1. 24列 事前予想CSV
2. 26列 予想根拠明細CSV（全R×6艇）
3. 21列 2連単1点販売選別CSV

moduleのmanifestは監査補助物であり、通常のユーザー向け3成果物には数えない。

予想・販売freeze後、結果参照前に公式 `締切時刻` とfreeze日時をレース単位で比較する。freezeが締切予定日時以後なら予想を変更せず `CONTAMINATED` として真正forward集計から分離する。

### Control / Shadow

単日の結果でControlを途中変更しない。改善候補は別version / Shadowとして結果参照前に定義・freezeし、Controlを上書きしない。

会場選別、Shadow-S、PairGate、OpponentScore研究の運用原則は `docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md` を参照する。

## 5. 会場選別

会場選別は購入レース決定ではなく、当日どの会場の全RをForwardTrialへ通すかを決める探索母集団設計とする。

- 全R構造 / 2連単適格 / 販売選別を分けて評価する。
- 新規・未検証会場を適度に探索する。
- 開催日目やSG/G1を機械的に除外しない。
- 会場特性は補助・タイブレークに限定する。
- 締切時刻を会場選別には使わない。
- 少数標本・単日結果だけで昇格/降格しない。
- 無料枠不足を理由に弱いレースを強制採用せず、必要なら探索母集団を広げる。

台帳が直近日まで完全更新されていない場合は、`FT2_取込管理` と `FT2_集計監査` で確認できる最新の真正完了世代までを根拠とし、未完了日の成績を手計算で正式評価へ混ぜない。

## 6. 結果取得

`src/fetch_boatrace_results.py` を中心に、freeze済み事前予想と公式結果を照合する。

- 結果取得工程は結果CSV・取得ログの生成と監査まで。
- Google Sheets台帳記帳は別工程。
- 対象日だけが示され、予想CSVがスレッドにない場合はDrive `predictions` のfreeze済み正本を検索する。
- 対象日・会場集合・仕様版で一意に決められなければ推測しない。
- 結果取得のために事前予想を再生成しない。

Dを使った場合はrequest ID、Issue、run、artifact、head SHA、input SHA、validationを追跡可能にする。

## 7. Google Sheets台帳の基本不変条件

- `対象日` を現在日付や処理実行日から生成しない。
- 予想確定日時 / 販売選別確定日時を結果取込時刻で上書きしない。
- 日跨ぎ後でもcurrent datetimeを対象日やfreezeの生成元に使わない。
- Published / 掲載成績は有料+無料のみ。CSVのみを混ぜない。
- 構造KPIは条件付き分母とする。
- 失敗構造は `的中` / `1号艇頭失敗` / `2着候補2艇外` / `内側1点選択ミス` / `返還` / `対象外`。
- 締切後freeze行は削除せず監査に残し、Genuineから分離する。
- Google Sheetsへ書込む前に日次原本・stable key・freeze・source整合性を検証する。

## 8. ForwardTrial専用分析台帳

`FT2_全R明細` を派生集計の唯一の正本とする。物理最終行ではなく非空 `FT2_ID` をデータ件数として扱う。

主キーは `日付×会場×R×仕様版`。同一キーは追記せずupsertする。

集計層:

- Raw: ForwardTrial対象
- Genuine: Rawかつ締切前freeze
- Published: Genuineかつ有料または無料

### Atomic Aggregate Set

次の9タブは1世代として扱う。

1. `FT2_日別集計`
2. `FT2_会場別集計`
3. `FT2_会場日目別集計`
4. `FT2_グレード別集計`
5. `FT2_判定構造別集計`
6. `FT2_販売選別検証`
7. `FT2_Score検証`
8. `FT2_Freeze監査`
9. `FT2_ダッシュボード`

全R明細更新後は9タブを全GENUINE明細から上書き全再生成する。前日値への加算、一部タブだけの通常更新は禁止する。

`FT2_集計監査` に各9タブの deterministic `aggregate_generation_id`、source raw/genuine/contaminated/exacta件数、max対象日、出力行数、検証状態を記録する。

9タブのgeneration / source件数が一致しない場合は `集計不整合` とする。

開催グレードはBOAT RACE公式日別レース一覧からFreezeし、未取得は推測せず `未分類 + 要確認`。G1/SGは除外せず分析軸にする。

## 9. 日次台帳記帳の標準経路

日次台帳記帳は結果取得とは別の完結工程とし、**Work / 接続済みGoogle Drive・Google Sheetsの直結経路**を標準とする。

Googleサービスアカウント、`GPT_GDRIVE_SERVICE_ACCOUNT_JSON`、旧台帳import Issue / Actions、旧 `run_forward_trial_chat_import.py` は使用しない。

開始時に読む:

- `docs/ForwardTrial_Chat日次台帳記帳運用.md`
- `src/forward_trial_analysis_import.py`
- `src/forward_trial_chat_ledger.py`

標準手順:

1. Driveの種別別フォルダから対象日のracecard / prediction / sales-selection / resultを特定し、4 file IDを固定する。
2. 対象日、会場集合、仕様版、キー、freeze、sourceをfail-closedで検証する。
3. `forward_trial_analysis_import.py` で正規化・真正性・grade/freeze監査用データを生成する。
4. `forward_trial_chat_ledger.py` で既存Sheets値と合わせ、stable-key upsert、Atomic Aggregate Set全再生成、既存販売台帳mirrorの決定論的書込計画を作る。
5. 接続済みGoogle Sheetsへ直接writeする。本体write中は `集計再生成中`。
6. `FT2_全R明細`、Atomic Aggregate Set、`FT2_集計監査`、既存販売台帳mirrorをread-backする。
7. FT2_ID重複0、9タブ同一generation/source、掲載=有料+無料、grade整合、formula error 0を確認する。
8. 全条件成立後にのみ `FT2_取込管理=完了` とする。

1タブでも世代・母数・書込に不一致があれば `集計不整合`、grade未解決等は `要確認`、例外は `エラー` とする。

再実行はstable-key upsertと全再生成でidempotentとし、件数・投資・回収を二重加算しない。

明細が存在する、日別集計に当日がある、`FT2_取込管理` に文字列 `完了` がある、という単独条件だけで完了扱いしない。

## 10. CSV原本保存・月締めParquet

日次CSV原本保存は生成・台帳とは別の保全工程とする。

- 会話添付 → ChatGPT Library → 参照可能な日次成果物の順に探索する。
- 見つからない原本を再生成しない。
- Driveの対応種別へ内容を変更せず保存する。
- 同名・同内容は再アップロードしない。
- 同名異内容は上書きせず競合として扱う。
- 当月はCSVを作業正本とし、日次Parquet化しない。
- 閉鎖月は`src/monthly_parquet_archive.py`でfamily × month × schema hashのZSTD level 3 Parquetとmanifestを生成する。schema差は統合せず、全元列はstring、`source_csv`は必須。
- Parquet生成、manifest、Lossless、業務キー、SHA、Drive upload、Drive存在、再取得・読込、manifest uploadの全PASSを確認して初めて`cleanup_ready=true`とする。
- `cleanup_ready`でない月のCSV/ZIPは削除しない。修正版は対象月CSVから新generationを再生成し、行単位編集しない。
- 詳細な命名・Drive配置・状態管理は`docs/Parquet月締め運用.md`を参照する。

詳細は `.gpt/HANDOFF.md` を参照する。

## 11. 改修時の回帰確認

コード変更時は対象moduleのtestsに加え、必要に応じて次を実行する。

```bash
python -m unittest discover -s boat-racing/tests -v
```

最低限、次を回帰確認する。

- 対象日・日跨ぎ
- freeze保持
- source/date/key不一致fail-closed
- 掲載とCSVのみの分離
- 条件付き構造KPI
- stable-key idempotency
- Atomic Aggregate Set同一generation
- 既存日不変

文書だけの変更ではPythonテスト実行は必須としないが、記載path・module・workflowの存在と、README / CONTEXT / HANDOFF / WORKFLOW間の矛盾がないことを確認する。

## 12. スレッド引越し時の完了基準

新しいスレッドが会話履歴なしでも、次を正本から復元できる状態を維持する。

- current prediction spec
- Git / Drive / Sheetsのsource of truth
- 工程境界
- 使用module / workflow
- 日次成果物のfreeze原則
- 台帳の完了判定
- 会場選別の思想
- Control / Shadowの分離
- 未完了日をどの正本から再判定するか

新スレッドで過去会話がないと再開できない情報が判明した場合は、会話メモリだけに残さず `HANDOFF.md` または対象docsへ戻す。

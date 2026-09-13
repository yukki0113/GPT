# Boat racing thread handoff

Updated: 2026-09-13

このファイルは、Chat / Workのスレッドが長大化して引っ越した場合に、会話履歴へ依存せず `boat-racing` プロジェクトを再開するための入口です。

## 1. 新スレッド開始時の読み順

latest `main` を確認し、原則として次の順に読む。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. 本 `HANDOFF.md`
4. `boat-racing/.gpt/WORKFLOW.md`
5. 対象作業の `docs/` と `src/`
6. D. Actions-Native Executionを使う場合だけ対象 `.github/workflows/`

司令室・会場選別・仕様研究の場合は `docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md` も読む。

過去チャットの要約、添付ZIP、一時作業領域は補助情報であり、Git `main` のソース・仕様・運用文書の代わりにしない。

## 2. 正本と不変原則

- Python / tests / docs / config / workflowは GitHub `yukki0113/GPT` `main` を正本とする。
- 日次の公式出走表、事前予想、予想根拠、販売選別、結果CSVはGoogle Drive `data` を正本とする。
- 継続台帳・FT2分析はネイティブGoogleスプレッドシート `競艇note販売運用台帳` を正本とする。
- 日次成果物、ログ、HTMLキャッシュ、台帳はGitへcommitしない。
- 予想・販売選別freeze前に当該日の結果を参照しない。
- 結果参照後に事前予想、買い目、販売Score、販売順位、掲載区分を再生成・修正しない。
- 取得不能・解析不能・入力不正・公式未確定を成功扱いしない。推測補完しない。
- current datetimeを対象日やfreezeの生成元にしない。処理日時は監査用途だけに使う。

### Google Drive data

Parent Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`

- racecards: `1zg77_EqlcQon0bPmQK-nSKfzMhKWIscV`
- predictions: `1ZHNpPyVQPjs4UvWLhc5ocXFCwLF_ybY2`
- prediction-rationales: `10dqQg2aPBtBNnJkPwuPVPZ2dx8mQzUzi`
- sales-selection: `1mgsmcJXrKJtjYX8DbAGLsdqSdt5JWRrS`
- results: `1P60LF55o1P_1QUqdRd_cqAqLyDidTRUw`

### Google Drive analysis

Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`

### Ledger

- Spreadsheet: `競艇note販売運用台帳`
- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- timezone: `Asia/Tokyo`

Drive/Gitの旧Excel台帳は移行前スナップショットであり、正本へフォールバックしない。

## 3. 現在の前向き試行

2026-09-01以降は `ForwardTrial_Ver0.1` をControlとする。

開始時に次を読む。

1. `docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
2. `docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

前者を優先し、Ver1.2.1は基礎・履歴仕様として扱う。

日次予想の標準ユーザー向け成果物は、同一freeze時点の3CSV。

1. 24列 事前予想CSV
2. 26列 予想根拠明細CSV（全R×6艇）
3. 21列 2連単1点販売選別CSV

結果参照後にControlを遡及変更しない。Shadowを真正forwardとして扱う場合は、別version / 別資産として結果参照前に定義・freezeする。

## 4. 主要モジュール地図

- `src/fetch_boatrace_racelist_with_meta.py`
  - 公式出走表取得と開催メタ付与の標準入口。
- `src/fetch_boatrace_racelist.py`
  - BOAT RACE公式出走表を取得。
- `src/fetch_boatrace_event_meta.py`
  - 公式日別レース一覧から開催名・グレードを取得。
- `src/enrich_boatrace_racelist_metadata.py`
  - 既存出走表CSVへ開催名・開催グレードを付与。
- `src/fetch_boatrace_pre_race_info.py`
  - 直前情報取得。
- `src/forward_trial_predict.py`
  - ForwardTrialの事前予想・根拠明細・2連単1点販売選別を決定論的に生成。
- `src/fetch_boatrace_results.py`
  - BOAT RACE公式結果取得と事前予想照合。
- `src/ledger_daily_result_import.py`
  - 日次結果取込の基礎検証・JSON更新計画生成。
- `src/forward_trial_analysis_import.py`
  - ForwardTrial専用分析の正規化、真正性、freeze/grade、集計値生成。
- `src/forward_trial_chat_ledger.py`
  - stable-key upsert、FT2全再集計、`FT2_集計監査`、既存販売台帳mirrorのconnector-neutral書込計画生成。

**廃止済み:** 旧 `run_forward_trial_chat_import.py`、旧台帳import Issue / Actions、Googleサービスアカウント経路を現行運用へ戻さない。

## 5. GitHub実行経路

毎回 A/B/C/D を判定する。

- A Read/Audit: GitHubのread/search、commit/issue/workflow/artifact/SHA確認。Issue不要。
- B Git Change: source/test/docs/config/workflowのUTF-8テキスト変更。direct commit。Issue不要。
- C Pure Deterministic Execution: Git正本module+入力をChat側で同一条件実行可能な処理。
- D Actions-Native Execution: Secrets、公式外部取得、artifact chain、特殊runner、監査run等が本当に必要な処理。

現役の競艇D経路:

- 出走表: `.github/workflows/boatrace_racelist_issue.yml`
- 直前情報: `.github/workflows/boatrace_pre_race_issue.yml`
- 結果取得: `.github/workflows/boatrace_results_chat.yml`

台帳記帳はDではない。Work / 接続済みDrive・Sheets直結を使う。

Issueを作る場合は、latest main、共通contract、対象workflow/parser、必須値を先に検証し、1 requestにつきIssueを1回だけ発行する。失敗時にblind rerunしない。

## 6. 工程境界

### 会場選別 / 司令室

会場選別は購入レース決定ではなく探索母集団設計。全R構造、2連単適格、販売選別を分けて読む。新規会場、開催日目、SG/G1も分析軸として扱い、一律除外しない。締切時刻は会場選別には使わない。

詳細: `docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md`

### 出走表取得

公式出走表を取得・Freezeする。結果は見ない。

標準資料:

- `docs/出走表取得依頼_定型作業.txt`
- `docs/README_出走表取得.md`
- `src/fetch_boatrace_racelist_with_meta.py`

会場選別CSVの `位置づけ` は司令室説明用であり、取得requestの仕様に不要なら混入させない。

### 事前予想

freeze済み公式出走表を入力に `forward_trial_predict.py` を使う。結果参照前に3CSVを確定し、Drive対応フォルダへ保存する。

### 公式結果取得・予想照合

`fetch_boatrace_results.py` でfreeze済み事前予想と公式結果を照合する。この工程では台帳を書き換えない。

標準資料:

- `docs/結果照合取得依頼_定型作業.txt`
- `docs/README_公式結果取得.md`

### 日次台帳記帳

結果取得とは別の完結工程。

標準資料:

- `docs/ForwardTrial_Chat日次台帳記帳運用.md`
- `src/forward_trial_analysis_import.py`
- `src/forward_trial_chat_ledger.py`

WorkがDrive種別別フォルダからracecard / prediction / sales-selection / resultの4 file IDを固定し、Git正本moduleで決定論的書込計画を作り、接続済みGoogle Sheetsへ直接write/read-backする。

Googleサービスアカウント、台帳import Issue / Actionsを起動しない。

### ForwardTrial分析

FT2の14タブを使う。`FT2_全R明細` を派生集計正本とし、Atomic Aggregate Set 9タブを同一generationで全再生成する。

詳細: `docs/競艇note販売運用台帳_ForwardTrial専用分析台帳.md`

## 7. FT2完了判定

Atomic Aggregate Set:

1. `FT2_日別集計`
2. `FT2_会場別集計`
3. `FT2_会場日目別集計`
4. `FT2_グレード別集計`
5. `FT2_判定構造別集計`
6. `FT2_販売選別検証`
7. `FT2_Score検証`
8. `FT2_Freeze監査`
9. `FT2_ダッシュボード`

`FT2_集計監査` で9タブの `aggregate_generation_id`、source raw/genuine/contaminated/exacta件数、max対象日等を照合する。

`FT2_取込管理=完了` は、少なくとも以下が全成立した場合のみ。

- Drive原本整合
- stable key重複0
- frozen列矛盾なし
- Atomic Aggregate Set全再生成成功
- 9タブ同一generation/source
- 既存販売台帳mirror成功
- 掲載=有料+無料
- grade整合
- formula error 0
- read-back一致

明細がある、日別に最新日がある、取込管理に文字列「完了」がある、のいずれか単独では完了とみなさない。

状態は `取込中` / `明細取込済` / `集計再生成中` / `集計不整合` / `要確認` / `完了` / `エラー` を使う。

再実行はidempotentとし、前日集計への加算でなく全明細から再生成する。

## 8. 結果取得スレッドの再開

1. latest mainと本HANDOFFを確認。
2. 結果取得docs / moduleを確認。
3. 当該日のfreeze済み事前予想CSVを特定。
4. 対象日、会場集合、件数、必須列、キー一意性を確認。
5. C/Dを判定。
6. Dなら対象workflowのrequest contractを確認してIssueを1回だけ作成。
7. RESULT / run / artifactを回収し再監査。
8. 結果CSVと取得ログを返す。台帳更新はしない。

freeze済み事前予想は、当該スレッド添付があれば優先し、なければDrive `predictions` から対象日・会場集合・`ForwardTrial_Ver0.1` が一致する正本を探す。複数候補で正本を一意に決められなければ推測しない。結果取得のために事前予想を再生成しない。

## 9. CSV原本保存・月次圧縮

CSV保全は予想・結果・台帳とは別工程。

探索順:

1. 会話添付
2. ChatGPT Library
3. 参照可能な日次成果物

GitHubに日次CSVがないことを未生成の根拠にしない。対象ファイルが見つからなければ再生成せず未発見として報告する。

アップロード前にDriveの同名・内容を確認し、同名同内容は再アップロードしない。同名異内容は上書きせず競合として扱う。アップロード後もDrive上の存在を確認して完了とする。

月次ZIP化と元CSV削除は、ユーザーが月・区分・削除を明示した場合のみ。

1. 対象CSVを全件列挙。
2. バイト列・ファイル名を変更せず区分ごとにZIP化。
3. ZIPテスト / 収録件数照合。
4. Driveへ保存し存在確認。
5. 確認済みZIP収録元CSVだけ削除。
6. 残存CSVとZIPを再確認。

## 10. 司令室・Shadow研究の引継ぎ

正本: `docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md`

固定思想:

- 会場選別は探索母集団設計。
- 全R / 適格 / 販売の3層を混ぜない。
- 少数標本や1日成績だけで会場を昇降格しない。
- SG/G1や初日/最終日を一律除外しない。
- Controlは `ForwardTrial_Ver0.1` のまま結果後変更しない。
- Shadowは結果前freezeしたものだけを真正forward比較とする。
- 結果後の再分類は研究バックテストであり、Shadow forward実績にしない。
- 台帳が未完了の日は正式な会場選別根拠へ混ぜない。

研究候補（Control未採用）:

- Shadow-S: 販売順位1〜3位有料、4〜6位無料、7位以下CSV
- PairGate
- OpponentScore再研究

研究候補は将来変更され得るため、実行時に上記正本文書と最新仕様を再確認する。

## 11. スレッド引越し時の最小チェックリスト

- latest main commit
- active prediction spec
- Git / Drive / Sheetsのsource of truth
- 対象工程の担当境界
- 使用module / workflowの実在
- 入力原本の所在 / ID / 必要なSHA
- 日次予想3CSVのfreeze整合性
- FT2最新完了世代
- Control / Shadow境界
- 未完了状態はDrive / Sheets / 必要な場合のみActionsから再判定

累計成績や「どこまで記帳済みか」のような変動状態をこのファイルへ固定しない。

## 12. 更新ルール

次が変わった場合は本HANDOFFへの影響も確認する。

- source of truth
- active prediction spec
- 日次フォルダ構成
- 主要moduleの追加 / 廃止 / 役割変更
- GitHub実行経路 / Issue contract
- 結果取得と台帳記帳の担当境界
- 台帳の認証I/O経路
- 日次予想の標準成果物 / freeze運用
- 会場選別 / Shadowの恒久思想
- 新スレッドで会話履歴がないと再開できない事象

引継ぎに必要な情報は会話メモリだけに残さず、再現可能な範囲をGit正本へ戻す。

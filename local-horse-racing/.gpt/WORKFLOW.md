# local-horse-racing workflow

## Read first

作業開始時は、次の順で正本を確認する。

1. リポジトリ共通 `.gpt/GITHUB_OPERATION_POLICY.md`
2. リポジトリ共通 `.gpt/README.md`
3. 本ディレクトリの `README.md`
4. 本ディレクトリの `.gpt/CONTEXT.md`
5. 本ディレクトリの `.gpt/WORKFLOW.md`
6. `docs/CANONICAL_DATA_SPEC.md`
7. 対象source / test / docs / workflow
8. Parquet / DuckDB処理を扱う場合はリポジトリ共通 `tools/data-storage/README.md`

`.gpt/ISSUE_REQUEST_CONTRACTS.md` は Actions-native 実行（下記D）を選ぶ場合に確認する。

Driveデータ正本ルートは `/GPT/local-horse-racing/`。
folder URL: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

## GitHub operation policy

GitHubへのアクセス・更新・実行経路は、上位正本 `.gpt/GITHUB_OPERATION_POLICY.md` の A/B/C/D ルーティングに従う。

### A. Read / Audit

repository / file / commit / issue / workflow / run、差分、SHA等の確認はGitHubから直接 read / search / fetchする。確認だけのためにIssue / Actionsを起動しない。

### B. Git Change

source / test / docs / config / workflow等のUTF-8テキスト変更は、原則としてGitHubへ直接反映する。

```text
latest main確認
-> 対象path / 現在内容 / blob SHA確認
-> 必要差分のみ作成
-> direct create / update / delete
-> remote commit確認
```

通常のGit変更に `[gpt-git-update]` Issueを使わない。Issue経路はdirect write不能時の互換フォールバックとする。

### C. Pure Deterministic Execution

GitHub正本moduleと必要入力をGPT側で取得でき、secret・特殊runner・正式Actions監査証跡を必要としない決定的処理は、GPTローカル実行を第一候補とする。

対象例:

- NAR ZIP / CSVのschema・row-count・SHA・integrity確認
- canonical parser / splitterの実行
- field catalog / race status / as-of evidence生成
- 固定入力に対するCSV / JSON整形・join・集計
- Parquet変換・validation・DuckDB query・benchmark（`tools/data-storage/` を利用）
- focused unit test / regression
- 既存成果物の比較・監査

Parquet / DuckDB処理は、原則として共通 `tools/data-storage/` のmodule / CLIを利用し、local-horse-racing側で同等実装をコピーしない。Project固有のcolumns / keys / partitions / as-of rulesだけをProject側へ定義する。

正本moduleと同等の処理を独自再実装して置き換えず、可能なら source commit / input SHA / output SHA / module version等を残す。

### D. Actions-Native Execution

Issue / GitHub Actionsは、GitHub Secrets、認証付き外部取得、Actions artifact chain、長時間・大容量runner、immutable freeze / publication / release、run ID / artifactを正式監査証跡として固定する必要がある場合等に限定する。

Dを選ぶ場合は `.gpt/ISSUE_REQUEST_CONTRACTS.md` に従ってIssue発行前preflightを完了し、failed stepを確認せずblind retryしない。

## Concurrent write safety

複数Chat / Workが同じ `main` を並行更新する前提で扱う。

- force push / force ref updateは禁止。
- 既存file更新は取得済みblob SHAを条件として行う。
- stale SHA / conflict / non-fast-forward時はlatest `main` と対象fileを再取得する。
- 先行変更を保持したまま、自スレッドの未反映差分だけを最新内容上へ再構築する。
- 古い全文の機械的再送で他スレッドの変更を上書きしない。

## Phase 0 raw standard flow

1. 対象年月と `race` / `odds` を指定する。
2. `python -m nar.download.monthly` でNAR公式月次ZIPを取得する。
3. ZIPとして開けること、想定ファイルが揃うこと、CSVヘッダーが公式スキーマと一致することを検証する。
4. raw ZIPのSHA-256を算出する。
5. raceは `/GPT/local-horse-racing/00_raw/race/`、oddsは `/GPT/local-horse-racing/00_raw/odds/` へ原本バイト列のまま保存する。
6. auditを保存する場合は `/GPT/local-horse-racing/20_audit/` を使用する。
7. rawを変更する必要が生じた場合は上書きせず、原因を調査する。

## Phase 1 canonical standard flow

1. raw race ZIPを読み、公式headerを再検証する。
2. `nar.canonical.field_catalog` に従い `PRE_SAFE` / `PRE_ASOF_PENDING` / `POST_ONLY` を分離する。
3. `nar.canonical.parser` で `pre_race` / `pre_runner` / `pre_runner_history_snapshot` / `post_race_result` / `post_runner_result` / `post_payout` / `control_race_status` を生成する。
4. history snapshotは常に `PENDING_VALIDATION` で開始し、モデル特徴量へ自動露出しない。
5. `nar.canonical.leakage.validate_history_asof` で累積成績・最高タイムの前走→次走更新整合を検証する。
6. staging CSVからParquetへ変換する場合は `nar.canonical.storage` 経由で `tools/data-storage/data_storage.runner.run_config` を利用する。
7. ParquetはZSTD、`race_year` Hive partition、canonical key unique / row count / schema / NULL validationを基本とする。
8. canonicalとauditはDriveへ保存する。staging CSVは再生成可能な一時物であり長期正本にしない。
9. 広期間as-of監査が完了するまで `PRE_ASOF_PENDING` を `VERIFIED_ASOF` 相当へ昇格しない。
10. バックテスト・モデルはraw / postを特徴量入力として直接参照しない。

## Commands

Raw取得:

~~~bash
cd local-horse-racing
python -m nar.download.monthly --year YYYY --month M --kind race --output-dir <drive-root>/GPT/local-horse-racing/00_raw/race --audit-dir <drive-root>/GPT/local-horse-racing/20_audit
python -m nar.download.monthly --year YYYY --month M --kind odds --output-dir <drive-root>/GPT/local-horse-racing/00_raw/odds --audit-dir <drive-root>/GPT/local-horse-racing/20_audit
~~~

Canonical staging + as-of evidence:

~~~bash
cd local-horse-racing
PYTHONPATH=. python -m nar.canonical.build \
  --input <monthly-race.zip-or-year-wrapper.zip> \
  --staging-dir <staging-dir> \
  --validate-asof
~~~

Canonical Parquet:

~~~bash
# repository root
PYTHONPATH="local-horse-racing:tools/data-storage" \
python -m nar.canonical.build \
  --input <monthly-race.zip-or-year-wrapper.zip> \
  --staging-dir <staging-dir> \
  --parquet-dir <drive-root>/GPT/local-horse-racing/10_canonical \
  --audit-dir <drive-root>/GPT/local-horse-racing/20_audit/canonical \
  --validate-asof
~~~

## Validation

Project tests:

~~~bash
cd local-horse-racing
python -m unittest discover -s tests -v
python -m py_compile nar/download/*.py nar/schema/*.py nar/canonical/*.py
~~~

共有Parquet / DuckDB tool tests:

~~~bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python -m pytest tools/data-storage/tests -q
~~~

実データsmokeではまず1か月等の小範囲でrow count、race status、as-of evidenceを確認し、その後に年単位・10年単位へ広げる。

## Current scope stop

以下は別途明示的に進めるまで実装しない。

- `PRE_ASOF_PENDING` の無監査自動昇格
- 馬・騎手・調教師の完全な恒久ID名寄せ
- 派生as-of特徴量の量産
- 指数・モデル・予想
- odds市場期待値ロジック
- 自動定期実行・販売運用

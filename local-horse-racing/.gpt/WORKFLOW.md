# local-horse-racing workflow

## Read first

作業開始時は、次の順で正本を確認する。

1. リポジトリ共通 `.gpt/GITHUB_OPERATION_POLICY.md`
2. リポジトリ共通 `.gpt/README.md`
3. 本ディレクトリの `README.md`
4. 本ディレクトリの `.gpt/CONTEXT.md`
5. 本ディレクトリの `.gpt/WORKFLOW.md`
6. 対象source / test / docs / workflow

`.gpt/ISSUE_REQUEST_CONTRACTS.md` は Actions-native 実行（下記D）を選ぶ場合に確認する。

Driveデータ正本ルートは `/GPT/NAR/`。
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
- 固定入力に対するCSV / JSON整形・join・集計
- focused unit test / regression
- 既存成果物の比較・監査

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

## Phase 0 standard flow

1. 対象年月と `race` / `odds` を指定する。
2. `python -m nar.download.monthly` でNAR公式月次ZIPを取得する。
3. ZIPとして開けること、想定ファイルが揃うこと、CSVヘッダーが公式スキーマと一致することを検証する。
4. raw ZIPのSHA-256を算出する。
5. raceは `/GPT/NAR/00_raw/race/`、oddsは `/GPT/NAR/00_raw/odds/` へ原本バイト列のまま保存する。
6. auditを保存する場合は `/GPT/NAR/20_audit/` を使用する。
7. rawを変更する必要が生じた場合は上書きせず、原因を調査する。

## Current command

~~~bash
cd local-horse-racing
python -m nar.download.monthly --year YYYY --month M --kind race --output-dir <drive-root>/GPT/NAR/00_raw/race --audit-dir <drive-root>/GPT/NAR/20_audit
python -m nar.download.monthly --year YYYY --month M --kind odds --output-dir <drive-root>/GPT/NAR/00_raw/odds --audit-dir <drive-root>/GPT/NAR/20_audit
~~~

## Validation

~~~bash
cd local-horse-racing
python -m unittest discover -s tests -v
python -m py_compile nar/download/*.py nar/schema/*.py
~~~

## Scope stop

以下はユーザーが明示的に次Phaseへ進めるまで実装しない。

- 全期間バックフィル
- canonical DB / parquet等への変換
- 馬・騎手・調教師の名寄せ
- as-of特徴量
- 指数・モデル・予想
- 自動定期実行

# local-horse-racing workflow

## Read first

作業開始時はリポジトリ共通 `.gpt/README.md` と `.gpt/ISSUE_REQUEST_CONTRACTS.md`、本ディレクトリの `README.md` / `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` を確認する。

Driveデータ正本ルートは `/GPT/NAR/`。
folder URL: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

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

## Git update route

Chat / Workから直接pushできない場合は、リポジトリ共通 `[gpt-git-update]` Issue経路を使用する。
最新main基準のunified diffを作り、可能な環境では `.gpt/tools/gpt_issue_preflight.py` と `git apply --check` を通してからIssueを作成する。

## Scope stop

以下はユーザーが明示的に次Phaseへ進めるまで実装しない。

- 全期間バックフィル
- canonical DB / parquet等への変換
- 馬・騎手・調教師の名寄せ
- as-of特徴量
- 指数・モデル・予想
- 自動定期実行

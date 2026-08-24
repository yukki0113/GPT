# 直前情報取得 GitHub Actions運用

## 目的

Chat実行環境からBOAT RACE公式サイトへ直接通信できない場合に、GitHub Actionsを正式な代替実行経路として使用する。

実行場所だけをGitHub側へ移し、取得ロジックはGit正本のPythonをそのまま使用する。Actions専用の取得ロジックは作らない。

## 正本

Repository: `yukki0113/GPT`
Branch: `main`

使用資産:

- `boat-racing/src/fetch_boatrace_pre_race_info.py`
- `boat-racing/docs/README_直前情報取得.md`
- `boat-racing/docs/直前情報取得依頼_定型作業.txt`
- `boat-racing/requirements.txt`
- `boat-racing/requirements_直前情報取得.txt`
- `.github/workflows/boatrace_pre_race_manual.yml`

## Workflow

`.github/workflows/boatrace_pre_race_manual.yml`

`workflow_dispatch` の入力:

- `date`: 対象日 `YYYYMMDD`
- `venue`: 会場名または公式会場コード（例: `三国` / `10`）
- `race`: R番号 `1`〜`12`
- `format`: `json` / `csv`。通常運用は `json`

## Actions側の処理

1. `main` をcheckoutする。
2. Python 3.12をセットアップする。
3. `boat-racing/requirements.txt` をインストールする。
4. 入力値を検査する。
5. `boat-racing/src/fetch_boatrace_pre_race_info.py` をそのまま実行する。
6. 成果物と `run_status.txt` をartifact化する。
7. fetcherが失敗した場合もartifact upload後にWorkflowを失敗扱いにする。

## artifact

基本名:

`boatrace-pre-race-<date>-<venue>-<race>R-<run_id>`

artifact内:

- 取得JSONまたはCSV
- `run_status.txt`

`run_status.txt` には少なくとも以下を記録する。

- fetcherの終了コード
- date
- venue
- race
- format
- 実行元commit SHA (`source_sha`)

## Chat側の回収・検査

Actions実行後、Chat側で対象runのartifactを回収する。

通常のJSON運用では次を確認する。

1. UTF-8で有効なJSONである。
2. `fetch_status == success` である。
3. `racecard_racers` が6艇ある。
4. 展示タイムが6艇ある。
5. `weather.start_exhibition` が6艇ある。
6. 全start_exhibition要素に `exhibition_course`、`boat_number`、`start_exhibition_st` がある。
7. 気温・水温・天候・風向・風速・波高が必須条件を満たす。
8. 結果・払戻・オッズ由来の情報が混入していない。
9. `run_status.txt` の終了コードと `source_sha` を確認する。

取得失敗時は `failure_kind` と `failure_message` を確認し、通信失敗、直前情報未公開、必須項目欠損、HTML構造変更等を区別する。

## Git管理対象外

次は日次成果物でありGitへcommitしない。

- 取得JSON/CSV
- `run_status.txt`
- Actions artifact
- 実行ログ
- HTMLキャッシュ
- その他の日次出力

Gitへ反映するのは、取得ロジック、README、requirements、Workflow、恒常的な作業手順を変更した場合だけとする。

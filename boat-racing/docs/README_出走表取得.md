# BOAT RACE公式出走表CSV取得ツール

BOAT RACE公式サイトのPC版出走表をHTTP取得して解析し、失敗時のみスマホ版へフォールバックするPythonツールです。予想・買い目・オッズ・展示・直前情報・結果・払戻は取得も出力もしません。

## 事前準備

- Windows 10/11、Python 3.10以上
- `py -3 -m pip install -r requirements.txt`

## 実行

`py -3 fetch_boatrace_racelist.py --config config_20260801.json`

または `run_20260801.bat` をダブルクリックします。設定JSONの `date`、`venues`（`name`、2桁の`code`、`day`）、`output_dir` を変更すれば、ソース改修なしで別日・別会場を取得できます。

実行中は、会場の開始、各レースの「取得中」「完了」、会場ごとの完了件数、CSV出力の開始・完了をコマンドプロンプトに表示します。通常は1レースあたり数秒～十数秒かかります。

### リクエスト間隔と処理時間ログ

`request_interval_seconds` は、**HTTPリクエスト開始時刻どうしの最小間隔**として扱います。標準値は1.0秒です。前のHTTP応答が1秒以上かかった場合は、応答完了後に追加で1秒待たず、そのまま次のリクエストを開始します。これにより、直列取得と最低開始間隔を維持したまま不要な待機を避けます。

一時的なHTTPエラー・通信例外の再試行時は、従来どおり `Retry-After` と指数バックオフを優先します。通常取得を並列化する変更ではありません。

取得ログには、各HTTPリクエストについて `http_seconds` と `rate_limit_wait_seconds`、各レースについて `parse_seconds` / `race_seconds`、実行終了時に `timing_summary` としてHTTP合計・解析合計・レート制御待機合計・全体所要時間を記録します。処理時間の悪化を調査する場合は、まずこの内訳を確認してください。

## Chatからの標準実行（GitHub Issue経由）

Chatからの日次取得は、GitHub Issueを実行要求として使う方式を標準とします。

- Workflow: `.github/workflows/boatrace_racelist_issue.yml`
- Issue title: `[BOATRACE_RACELIST_REQUEST] <request_id>`
- Issue body: raw JSON
- RESULT marker: `BOATRACE_RACELIST_RESULT`
- artifact名: `boatrace-racelist-<request_id>-<run_id>`
- 処理終了後、Request Issueは自動Close
- artifact保持期間: 14日

Issue本文例:

```json
{
  "date": "20260825",
  "venues": [
    {"name": "常滑", "code": "08", "day": "4日目"},
    {"name": "三国", "code": "10", "day": "2日目"}
  ],
  "request_interval_seconds": 1.0
}
```

WorkflowはIssue本文をJSONとして検証し、Git正本の `boat-racing/src/fetch_boatrace_racelist.py` を通常CLIとして実行します。Issue本文をshellへ直接展開せず、解決済み設定を `resolved_request.json` に保存します。

GitHub ActionsのPythonセットアップでは `boat-racing/requirements.txt` をキーにpipキャッシュを利用し、毎回のpip自己更新は行いません。依存関係の内容は変えず、起動準備時間だけを軽量化します。手動fallback workflowも同じキャッシュ設定を使用します。

artifactには通常、以下を含めます。

- 予想入力CSV
- 原本CSV
- 取得状況CSV
- 取得ログ
- `resolved_request.json`
- `run_status.txt`
- `validation_report.json`

Chat側はIssueコメントのRESULT JSONから `status`、`run_id`、`artifact_name` を取得し、artifactを回収して検査後に日常成果物を返却します。

`.github/workflows/boatrace_racelist_manual.yml` は手動フォールバックとして残しますが、Chatからの通常運用ではIssue経由を優先します。

## 出力

指定フォルダへ以下を都度**上書き再生成**します（追記しません）。

- `日付_公式出走表原本_会場.csv`：監査列を含む31列
- `日付_公式出走表_会場.csv`：予想入力用19列（`R`の直後に公式の`締切時刻`を追加）
- `日付_出走表取得状況_会場.csv`：1レース1行の取得結果
- `日付_出走表取得ログ_会場.log`：HTTP状態、再試行、HTTP/解析所要時間、検査の記録

## 取得不能時

取得状況CSVの`取得状態`、`不足項目`、`エラー内容`とログを確認してください。必須項目が空欄なら成功扱いにせず、終了コード2で明確に通知します。HTTP 200でも本文・HTML形式・出走表構造・会場・場コード・日付・開催日目を検査し、取り違えや空ページを成功扱いにしません。PC版を解析できない場合はスマホ版を取得します。2026-08-01時点ではスマホ版のHTTP応答はJavaScript描画用の空コンテナであり、通常HTTPでの安全な抽出はできないため、フォールバックも`取得不能`として記録します。リクエスト開始間隔は標準1秒、一時的なHTTPエラーまたは通信例外だけを各URL最大2回再試行します。

## 公式サイト構造が変わった場合

PC版の解析は `fetch_boatrace_racelist.py` の `parse_pc`、スマホ版は `parse_sp` を修正します。コース別進入数・1/2/3着率は出走表ページに掲載がないため、推測で補完せず空欄です。スマホ版の構造差で必須項目を安全に抽出できない場合も成功扱いにしません。

# BOAT RACE公式出走表CSV取得ツール

BOAT RACE公式サイトのPC版出走表をHTTP取得して解析し、失敗時のみスマホ版へフォールバックするPythonツールです。予想・買い目・オッズ・展示・直前情報・結果・払戻は取得も出力もしません。

2026-09-11以降の標準入口では、出走表取得後にBOAT RACE公式の日別レース一覧も取得し、会場ごとの開催グレード・開催名を出走表CSVへ付与します。各Rページの公式タイトルは既存の `レース種別` を維持したまま、新設の `レース名` にも保存します。

## 事前準備

- Windows 10/11、Python 3.10以上
- `py -3 -m pip install -r requirements.txt`

## 実行

標準入口:

`py -3 fetch_boatrace_racelist_with_meta.py --config config_20260801.json`

内部では次の順に実行します。

1. `fetch_boatrace_racelist.py` で対象会場1R〜12Rの公式出走表を取得
2. `enrich_boatrace_racelist_metadata.py` で公式日別レース一覧から開催グレード・開催名を取得
3. 原本CSVと予想入力CSVへ `開催グレード`、`開催名`、`レース名` を付与

設定JSONの `date`、`venues`（`name`、2桁の`code`、`day`）、`output_dir` を変更すれば、ソース改修なしで別日・別会場を取得できます。

### 追加列

予想入力CSVは従来19列から22列へ拡張します。追加列は `開催日目` の直後です。

- `開催グレード`: `SG` / `G1` / `G2` / `G3` / `一般`
- `開催名`: 節全体の公式開催タイトル。例 `開設７４周年記念　海の王者決定戦`
- `レース名`: 各Rページの公式タイトル。例 `準優勝戦`、`優勝戦`、`予選`、`一般`

既存の `レース種別` は下流互換のため削除・改名せず、`レース名` と同じ各R公式タイトルを保持します。

開催グレード・開催名は推測せず、公式日別レース一覧で解決できなければメタデータ付与を失敗として終了コード2を返します。G3は `G3` として分類します。

### リクエスト間隔と処理時間ログ

`request_interval_seconds` は、出走表取得時のHTTPリクエスト開始時刻どうしの最小間隔として扱います。標準値は1.0秒です。

一時的なHTTPエラー・通信例外の再試行時は、`Retry-After` と指数バックオフを優先します。通常取得は直列のままです。

## Chatからの標準実行（GitHub Issue経由）

Chatからの日次取得は、Chat実行環境からBOAT RACE公式サイトへ同一条件で通信できない場合、GitHub Issue経由のActions-Native Executionを使用します。

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

WorkflowはIssue本文をJSONとして検証し、Git正本の `boat-racing/src/fetch_boatrace_racelist_with_meta.py` を実行します。Issue本文をshellへ直接展開せず、解決済み設定を `resolved_request.json` に保存します。

Actions側の出力検査では、予想入力CSVが22列であること、`開催グレード` / `開催名` / `レース名` が存在して全行非空であること、`レース名` と既存 `レース種別` が一致することを確認します。

artifactには通常、以下を含めます。

- 予想入力CSV
- 原本CSV
- 取得状況CSV
- 取得ログ
- `resolved_request.json`
- `run_status.txt`
- `validation_report.json`

`.github/workflows/boatrace_racelist_manual.yml` は手動フォールバックとして残し、同じメタデータ付き標準入口を使用します。

## 出力

指定フォルダへ以下を都度上書き再生成します（追記しません）。

- `日付_公式出走表原本_会場.csv`: 従来31列 + 追加3列 = 34列
- `日付_公式出走表_会場.csv`: 従来19列 + 追加3列 = 22列
- `日付_出走表取得状況_会場.csv`: 1レース1行の取得結果
- `日付_出走表取得ログ_会場.log`: HTTP状態、再試行、HTTP/解析所要時間、検査の記録

## 取得不能時

取得状況CSVの`取得状態`、`不足項目`、`エラー内容`とログを確認してください。必須項目が空欄なら成功扱いにしません。出走表本体が正常でも開催グレード・開催名を公式日別一覧から解決できない場合は、メタデータ付与工程を失敗として成功扱いにしません。

HTTP 200でも本文・HTML形式・出走表構造・会場・場コード・日付・開催日目を検査し、取り違えや空ページを成功扱いにしません。PC版を解析できない場合はスマホ版を取得します。

## 公式サイト構造が変わった場合

- 出走表PC版解析: `fetch_boatrace_racelist.py` の `parse_pc`
- スマホ版解析: `fetch_boatrace_racelist.py` の `parse_sp`
- 開催名・グレード解析: `fetch_boatrace_event_meta.py` の `parse_official_index`
- CSV付与: `enrich_boatrace_racelist_metadata.py`

公式表示から安全に取得できない項目を推測補完して成功扱いにはしません。

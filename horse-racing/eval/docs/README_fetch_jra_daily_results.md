# fetch_jra_daily_results

指定したJRA開催日の確定レース結果・払戻を取得し、1つのCSVへ出力するモジュールです。

## 目的

Eval表の検証および運用台帳への結果取込用として、開催日単位で以下を取得します。

- 会場
- R
- レース名
- 枠順確定時の出走頭数
- 1〜3着の馬番・馬名
- 各種払戻
- 取得元URL
- 取得状態・エラー詳細

## 正本

GitHub `yukki0113/GPT` の `main` ブランチにある以下を正本とします。

- `horse-racing/eval/src/fetch_jra_daily_results.py`
- `horse-racing/eval/src/validate_jra_results.py`
- `horse-racing/eval/requirements.txt`
- `.github/workflows/jra_results_manual.yml`

日次CSV、検証レポート、ログ等の実行成果物はGitへcommitしません。

## 取得元

Yahoo!スポーツの競馬ページを利用します。

- 月間開催スケジュール
- 開催日のレース一覧
- 各レース結果ページ

## 動作環境

- Python 3
- `requests`
- `beautifulsoup4`
- `urllib3`

```bash
pip install -r horse-racing/eval/requirements.txt
```

## 基本実行形式

### 日付を個別指定

```bash
python horse-racing/eval/src/fetch_jra_daily_results.py \
  --dates 2026-08-22 2026-08-23 \
  --output-dir output_20260822_23
```

### 期間指定

```bash
python horse-racing/eval/src/fetch_jra_daily_results.py \
  --from 2026-08-22 \
  --to 2026-08-23 \
  --output-dir output_20260822_23
```

### `--interval`

アクセス間隔を秒で指定します。既定値は `0.7` 秒です。

```bash
python horse-racing/eval/src/fetch_jra_daily_results.py \
  --dates 2026-08-22 \
  --interval 1.0
```

## 出力ファイル名

1日指定:

```text
YYYYMMDD_JRA結果払戻.csv
```

複数日・期間指定:

```text
YYYYMMDD-YYYYMMDD_JRA結果払戻.csv
```

文字コードはUTF-8 BOM付きです。

## CSV列

```text
日付,会場,R,レース名,出走頭数,1着馬番,1着馬名,2着馬番,2着馬名,3着馬番,3着馬名,単勝,複勝,枠連,ワイド,馬連,馬単,3連複,3連単,取得元URL,取得状態,エラー詳細
```

同一券種に複数の払戻行が存在する場合は ` / ` 区切りで1セルへ格納します。

## 出走頭数の重要仕様

`出走頭数` は「実際に走った頭数」ではなく、**取消・競走除外前の枠順確定時の頭数**を維持することを目的とします。

結果表で馬番が数値として存在する全行を対象とし、重複しない馬番数を出走頭数とします。着順が数値の行だけを数えてはいけません。

これは取消・競走除外馬も含むEval表作成時点に近い母数を保持するための仕様です。

## 払戻対象

- 単勝
- 複勝
- 枠連
- ワイド
- 馬連
- 馬単
- 3連複
- 3連単

## HTTP・エラー処理

各リクエストのタイムアウトは30秒です。以下のHTTPステータスは最大3回のリトライ対象です。

```text
429
500
502
503
504
```

### 終了コード

- `0`: 全レース取得成功
- `1`: 一部レースで取得・解析失敗
- `2`: 開催日レース一覧の通信・取得失敗
- `3`: `--dates` 指定日にJRA開催を検出できない

`--from` / `--to` の期間指定では、JRA開催のない日はスキップして処理を継続します。

## 正常終了の確認

最低限、以下を確認します。

- fetcherの終了コードが0
- 標準出力の `成功 N/N` が一致
- 全行で `取得状態=成功`
- `エラー詳細` が空
- `(日付, 会場, R)` に重複がない
- `出走頭数` が全行で正の整数
- 1〜3着の馬番・馬名が存在
- 単勝・複勝が全行で取得済み

土日通常開催では3場×12R×2日=72行が目安ですが、開催形態により変わるため固定値として扱いません。

## 機械検証

取得後は `validate_jra_results.py` を実行します。

```bash
python horse-racing/eval/src/validate_jra_results.py \
  output_20260822_23/20260822-20260823_JRA結果払戻.csv \
  --report output_20260822_23/validation_report.json
```

validatorは、列不足・空CSV・失敗行・キー重複・出走頭数異常・単勝/複勝欠損・成功行のエラー詳細混入・1〜3着欠損を検査します。

## GitHub Actionsによる代替実行経路

Chat実行環境からYahoo!スポーツへ直接通信できない、または通信が不安定な場合は、常設Workflow

```text
.github/workflows/jra_results_manual.yml
```

を使用します。

Workflowは `workflow_dispatch` から次のいずれかを指定します。

- `dates`: `2026-08-22 2026-08-23` のような個別日指定（空白またはカンマ区切り）
- `date_from` + `date_to`: 期間指定
- `request_interval_seconds`: 任意。既定 `0.7`

処理内容:

1. `main` をcheckout
2. `horse-racing/eval/requirements.txt` を導入
3. Git正本の `fetch_jra_daily_results.py` を実行
4. `validate_jra_results.py` でCSVを検証
5. CSV、`validation_report.json`、`run_status.txt` をartifact化
6. fetchまたはvalidationが失敗した場合はWorkflowを失敗扱いにする

artifact保持期間は14日です。日次成果物はGitへcommitしません。

## Chatスレッドでの標準運用

通常は以下の順で進めます。

1. GitHub `main` の最新状態を確認
2. `README.md`、`.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md`、本README、本体Pythonを確認
3. まず利用可能ならChat実行環境から直接実行
4. 直接通信不可または不安定な場合はGitHub Actionsへ切替
5. CSVをvalidatorで検証
6. 成果物をユーザーへ共有
7. 日次成果物はGitへcommitしない
8. ソース変更時のみ、テスト・差分確認・README更新・commit/pushを行う

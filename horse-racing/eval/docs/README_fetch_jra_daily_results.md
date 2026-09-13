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
- `.github/workflows/jra_results_chat.yml`
- `.github/workflows/jra_results_manual.yml`

日次CSV、検証レポート、ログ等の実行成果物はGitへcommitしません。

GitHub実行経路はroot `.gpt/GITHUB_OPERATION_POLICY.md` と `horse-racing/eval/.gpt/WORKFLOW.md` を上位正本とします。

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

## 実行経路 — C / D を開始時に判定

この処理はSecretsを必要としないため、Issue / Actions専用処理ではありません。

### C: Pure Deterministic Execution（通常可能なら優先）

次を満たす場合、GitHub mainのfetcher/validatorをChat/ローカルで直接実行します。

- 実行環境から取得先へ外部アクセス可能
- 対象期間が通常規模
- GitHub Actions run ID / artifactを正式監査証跡として固定する必要がない

```text
A: latest main / source確認
-> C: fetch_jra_daily_results.py
-> C: validate_jra_results.py
-> validation PASS
-> 必要な成果物を返却/台帳処理
```

「GitHubにworkflowが存在する」ことだけを理由にIssueを作りません。

### D: Actions-Native Execution

次の場合は `.github/workflows/jra_results_chat.yml` / `[JRA_RESULTS_REQUEST]` を使用します。

- Chat/ローカル環境から取得先へ到達できない
- 長期・大量取得でrunner実行が適切
- 取得/validation結果をimmutableなActions run / artifactとして監査保存したい
- 後続がActions artifact chainを正式に参照する

Issue title:

```text
[JRA_RESULTS_REQUEST] <request_id>
```

期間指定例:

```json
{
  "date_from": "2026-08-22",
  "date_to": "2026-08-23",
  "request_interval_seconds": 0.7
}
```

個別日指定例:

```json
{
  "dates": ["2026-08-22", "2026-08-23"],
  "request_interval_seconds": 0.7
}
```

D経路ではIssue作成前に `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を適用します。

Actions処理:

1. Issue作成イベントでActions起動
2. `main` checkout
3. requirements導入
4. fetcher実行
5. validator実行
6. CSV / validation / run status / resolved requestをartifact化
7. `JRA_RESULTS_RESULT` コメント
8. Issue close

成功条件:

```text
fetch_exit_code == 0
validation_exit_code == 0
validation.validation_status == success
```

artifact保持期間はworkflow設定に従います。日次成果物はGitへcommitしません。

### 実動確認履歴

2026-08-22〜2026-08-23で旧来のChat Issue経路を実動確認済みです。

- 72行取得 / 72行成功
- 失敗0 / 重複0
- 出走頭数異常0
- 単勝・複勝欠損0
- 1〜3着欠損0
- validation成功
- artifact / result comment / auto close確認

この履歴はD経路が動作することの証跡であり、「今後も常にDを使う」という意味ではありません。

## 予備経路

`.github/workflows/jra_results_manual.yml` はGitHub UIからの手動実行用です。通常はC/D判定後の適切な経路を使います。

## Chatスレッドでの標準運用

1. latest main、project README / WORKFLOW / HANDOFFを確認
2. Cで直接実行可能か判定
3. Cならfetch + validationを直接完結
4. Dが必要ならpreflight後に一意request_idでIssueを1回発行
5. DではRESULT / run / artifactをA: Read / Auditで確認
6. validation結果を必ず判定
7. 日次成果物はGitへcommitしない
8. source/workflow仕様変更時はdocs/testsと整合させる

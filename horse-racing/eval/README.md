# Eval表活用

中央競馬のEval表取得・OCR・検証運用を支援するPythonツール群です。

## Source of truth

GitHub `yukki0113/GPT` の `main` ブランチ配下 `horse-racing/eval/` をPython・README・作業手順の正本とします。

画像、OCR途中成果物、日次CSV、ログ等の運用成果物はGit管理対象外です。継続台帳のみ `ledger/Eval表集計・検証.xlsx` をGit管理し、GitHub `main` を正本とします。

## Current tools

- `src/master_eval_media_collector.py` — X上のEval表メディア収集
- `src/extract_eval_table.py` — Eval表画像を5列CSVへ変換するOCR親CLI
- `src/eval_ocr/` — 表構造検出・会場OCR・数値OCR・色検証・CSV出力
- `src/fetch_jra_daily_results.py` — JRA日次結果・払戻取得
- `src/validate_jra_results.py` — JRA結果CSVの機械検証

各ツールの詳細は `docs/` を参照してください。

## Eval表画像取得の標準実行経路

Chatからの依頼では `.github/workflows/eval_media_chat.yml` のGitHub Issue経路を標準とします。

Chat側で対象日の `@master_eval` 投稿を探索し、対象日と投稿IDの対応を確定したうえで、専用Issueを作成します。

- タイトル: `[EVAL_MEDIA_REQUEST] <request_id>`
- 本文: 対象日と投稿IDを記したJSON

Issue作成をトリガーにGitHub Actionsが起動し、Git正本の `src/master_eval_media_collector.py` を実行します。取得結果は `resolved_request.json`、`validation_report.json`、`run_status.txt`、投稿ID別の `metadata.json` と `media_XX.*` を含むartifactとして保存します。

完了時はActionsが同じIssueへ `EVAL_MEDIA_RESULT` 形式の機械可読コメントを返し、Issueを自動で閉じます。コメントには `run_id`、artifact名、collection/validation終了コード、対象日と投稿ID、検証結果が含まれます。

Actions側の取得検証は「各投稿でmetadataと1枚以上のmediaを取得できたか」までです。Eval表本体かどうかの判定は後段OCR側でも行います。

## Eval表OCRの標準実行経路

OCRは `src/extract_eval_table.py` を親CLIとして実行します。

- 2会場=24R、3会場=36Rを自動判定
- R番号はパネル位置から確定
- 馬番は表の行位置から確定
- 馬名セル画像は「その行に馬が存在するか」の画像判定だけに使用し、馬名文字列のTesseract OCRは行わない
- 会場名ヘッダーは日本語OCRを継続使用
- Evalは数値専用OCR
- 色付き上位セル、同色tie、色順位とEval大小の整合を検証
- `date + venue + race_no + horse_no` の重複、1〜12R構造、Eval 0〜100等を検証
- CSVとvalidation JSONを出力

通常出力CSVの契約は次の5列です。

```text
date,venue,race_no,horse_no,eval
```

`horse_name_ocr` は出力しません。正式馬名は後段のJRDB PACI enrichmentで `date + venue + race_no + horse_no` をキーに付与します。

日次運用の責務分担は次のとおりです。

```text
Eval OCR
  -> date,venue,race_no,horse_no,eval のみ取得

JRDB PACI enrichment
  -> 正式馬名・レース属性・馬属性を付与
```

GitHub Actionsでは `.github/workflows/eval_ocr_chat.yml` を使用します。

- タイトル: `[EVAL_OCR_REQUEST] <request_id>`
- 本文例:

```json
{
  "source_run_id": 32744761146,
  "source_artifact_name": "eval-media-...-32744761146"
}
```

`source_run_id` と `source_artifact_name` には、直前の `EVAL_MEDIA_RESULT` が返した画像取得artifactを指定します。

OCR workflowは取得artifact内の `resolved_request.json` を読み、各日付・投稿ID配下の画像を順にOCRへ投入します。Eval表レイアウトとして正常に構造解析・validationを通過した画像だけを成功候補とします。注意事項等の非Eval画像はレイアウト検出失敗として除外されます。

各対象日で成功候補がちょうど1枚の場合のみ成功とし、0枚または複数枚ならfailure/ambiguousとして扱います。

成果物artifactには、各画像から生成した5列CSV、個別validation JSON、全体の `batch_validation.json`、`resolved_request.json`、`run_status.txt` を含めます。完了時はIssueへ `EVAL_OCR_RESULT` コメントを返し、自動でIssueを閉じます。

OS側依存としてGitHub Actionsでは `tesseract-ocr` と `tesseract-ocr-jpn` をインストールします。日本語データは会場名ヘッダーOCRに必要です。Python依存は `horse-racing/eval/requirements.txt` を使用します。

## JRA結果取得の標準実行経路

Chatからの依頼では `.github/workflows/jra_results_chat.yml` を標準経路とします。

Chatは専用Issueを作成します。

- タイトル: `[JRA_RESULTS_REQUEST] <request_id>`
- 本文: 日付条件等を記したJSON

Issue作成をトリガーにGitHub Actionsが起動し、Git正本のPythonと `horse-racing/eval/requirements.txt` を使って取得・検証します。

完了時はActionsが同じIssueへ `JRA_RESULTS_RESULT` 形式の機械可読コメントを返し、Issueを自動で閉じます。コメントには `run_id`、artifact名、fetch/validation終了コード、validator結果が含まれます。Chatはそのコメントを読み、必要に応じてartifactを回収します。

これにより、Chat側の外部HTTPS通信可否や `workflow_dispatch` 起動APIの有無に依存せず、Chatから定型取得を開始・追跡できます。

## 予備経路

- `.github/workflows/eval_media_manual.yml` — Eval画像取得を人間がGitHub UIから `workflow_dispatch` する場合の予備経路
- `.github/workflows/jra_results_manual.yml` — JRA結果取得を人間がGitHub UIから `workflow_dispatch` する場合の予備経路
- Chat/ローカルから各Pythonを直接実行 — デバッグ・緊急時の補助経路

日常運用ではChat専用Issue経路を優先します。

日次画像、CSV、検証レポート、実行ログ等はGitへcommitしません。台帳更新時は最新mainの `ledger/Eval表集計・検証.xlsx` を更新し、バイナリ更新Issue経路で反映します。

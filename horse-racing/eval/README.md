# Eval表活用

中央競馬のEval表取得・OCR・検証・JRDB事前情報付与を支援するPythonツール群です。

## Source of truth

GitHub `yukki0113/GPT` の `main` ブランチ配下 `horse-racing/eval/` をPython・README・作業手順の正本とします。

画像、OCR途中成果物、日次CSV、ログ、JRDB Raw等の運用成果物は通常Git管理対象外です。

継続台帳は **ネイティブGoogleスプレッドシート `Eval表集計・検証`** を正本とします。

- Spreadsheet ID: `1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0`
- Chat / WorkからはGoogle Drive / Google Sheetsのnative操作で直接参照・更新する。
- 旧Google Drive Excel版およびGitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` は移行前スナップショットであり、最新台帳として使用しない。

## GitHub運用ルーティング — 2026-09-10

Issue / GitHub Actionsを一律の標準経路にはしません。処理開始時に「GitHub Actions環境が本当に必要か」を判定し、次の4系統から選びます。

| 経路 | 用途 | Evalでの代表例 |
|---|---|---|
| A: Read / Audit | GitHub上の状態確認 | main、file、commit、Issue RESULT、run、artifact metadata、SHA、diff確認 |
| B: Git Change | UTF-8テキスト変更 | Python、tests、README、`.gpt/`、workflowのdirect update/create/delete |
| C: Pure Deterministic Execution | Secrets等が不要な既存ロジックの直接実行 | Chatへ渡されたEval画像のOCR/validation |
| D: Actions-Native Execution | Secrets、artifact chain、長時間/大容量、immutable freeze、監査run等 | JRDB PACI認証取得+enrichment、取得時点をartifact固定するEval media collection |

A/B/Cで完結する処理のためだけにIssueを作成しません。DでIssue/Actionsを使用するときだけ、ルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を適用します。

## Current tools

- `src/master_eval_media_collector.py` — X上のEval表メディア収集
- `src/extract_eval_table.py` — Eval表画像を5列CSVへ変換するOCR親CLI
- `src/eval_ocr/` — 表構造検出・会場OCR・数値OCR・色検証・CSV出力
- `src/fetch_jra_daily_results.py` — JRA日次結果・払戻取得
- `src/validate_jra_results.py` — JRA結果CSVの機械検証
- `../jrdb/src/enrich_eval_csv_with_paci.py` — Eval OCR 5列CSVへJRDB PACI事前情報を付与
- `../jrdb/src/export_jrdb_eval_horse_results.py` — JRDB SED Raw → 「全馬データ」結果用1頭1行CSV + audit JSON

各ツールの詳細は `docs/` を参照してください。

## このスレッドの標準: Eval画像 -> 完成CSV

ユーザーがChatへEval表画像または画像ZIPを直接渡して「完成CSV」「CSV化」を依頼した場合の標準フローです。

```text
ユーザー画像
  -> C: Chat/ローカルでGitHub mainのEval OCRを実行
  -> OCR validation PASS
  -> 5列 date,venue,race_no,horse_no,eval
  -> D: [EVAL_PACI_ENRICH_REQUEST]
  -> Actions SecretsでPACIyymmdd.zip取得
  -> enrich_eval_csv_with_paci.py
  -> 完成CSV + audit artifact
  -> A: RESULT/run/artifactを直接確認・回収
  -> ユーザーへ返却
```

### OCR = C: Pure Deterministic Execution

OCRは `src/extract_eval_table.py` を親CLIとして行います。

- 2会場=24R、3会場=36Rを自動判定
- R番号はパネル位置、馬番は行位置から確定
- 馬名文字列のTesseract OCRは行わない
- 会場名ヘッダーは日本語OCR
- Evalは数値専用OCR
- 色付き上位セル・同色tie・固定色順位とEval大小をvalidation
- date + venue + race_no + horse_no の重複、1〜12R構造、Eval 0〜100等を検証
- OCR auditで再読候補やmanual review要否を確認

通常出力CSVの契約は5列です。

```text
date,venue,race_no,horse_no,eval
```

正式馬名はOCRせず、後段のJRDB PACI enrichmentで `date + venue + race_no + horse_no` をキーに付与します。

Chatへ直接画像が渡されている場合、OCR自体にはSecretsもGitHub artifact chainも不要なので、`.github/workflows/eval_ocr_chat.yml` のIssueを標準では使用しません。OCR validationがerrorならPACI enrichmentへ進みません。

OCRのみを明示された場合は5列CSVで停止して構いません。

### PACI enrichment = D: Actions-Native Execution

PACI enrichmentは引き続き `.github/workflows/eval_paci_enrich_chat.yml` と `[EVAL_PACI_ENRICH_REQUEST]` を使用します。

維持理由:

- PACI取得にGitHub Actions Secrets `JRDB_USER` / `JRDB_PASSWORD` が必要。
- 認証付きのJRDB有料原データをChatへ直接取得させない。
- PACI取得・結合・audit・artifactを同一run/head SHAへ固定できる。
- 完成CSVの監査runとして追跡性が必要。

Issueへ渡すのはOCR済み5列CSVのgzip+Base64 payloadであり、ユーザー画像自体はGitHubへ永続化しません。

正常完了では少なくとも次を確認します。

```text
fetch_exit_code == 0
enrich_exit_code == 0
collect_exit_code == 0
joined_horses == input_rows
unmatched_horses == 0
duplicate_keys == 0
```

`race_headcount_mismatches` は必ず監査し、0でなければ完成CSVと併せて明示します。PACI ZIPをユーザーへ再添付依頼しません。

## Eval表メディア取得

ユーザーが画像を直接添付済みなら、この工程はスキップします。

X投稿から新規取得し、取得時点のmetadata/media/validationを監査可能なartifactとして残す運用では、`.github/workflows/eval_media_chat.yml` / `[EVAL_MEDIA_REQUEST]` をD: Actions-Nativeとして維持します。

これはSecrets必須だからではなく、外部投稿の取得時点をrun + artifactへ固定し、後段が同一取得物を再利用できることに価値があるためです。

単発のRead確認でChat側に対象画像が既に存在し、取得artifactの固定が不要なら追加Issueは作りません。

## 既存media artifact -> OCR

`.github/workflows/eval_ocr_chat.yml` / `[EVAL_OCR_REQUEST]` は互換・監査用に残しますが、通常の第一選択ではありません。

通常はAでupstream RESULT/run/artifactを確認・回収し、規模が通常範囲ならCとしてChat/ローカルでOCRします。

次の場合のみDとして既存OCR workflowを使います。

- artifact chainをGitHub内で維持する必要がある
- immutable OCR audit runを残す必要がある
- 多数画像・長時間処理でChat/ローカル実行に不向き
- GitHub runner上のTesseract環境固定が再現性要件

## JRA結果取得

`src/fetch_jra_daily_results.py` / `src/validate_jra_results.py` はSecrets不要です。

- 外部アクセス可能な実行環境があり、通常規模で監査run不要ならCで直接実行可能。
- Chat/ローカルから取得先へ到達できない、長期・大容量、または取得run/artifactの固定が必要ならDとして `.github/workflows/jra_results_chat.yml` / `[JRA_RESULTS_REQUEST]` を使用する。

Dの場合は `fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とします。

出走頭数は取消・競走除外前の枠順確定時頭数を維持します。

## Git変更

Python、Markdown、JSON、YAML、tests、workflow等のUTF-8テキスト変更はB: Git Changeとして、原則ChatGPTからGitHubへdirect create/update/deleteでmainへ反映します。

変更前は必ず:

```text
latest main -> path存在確認 -> current content -> 必要差分
```

の順に確認します。`[gpt-git-update]` は互換fallbackであり標準経路ではありません。

変更後のcommit SHA、差分、CI/run状態はA: Read/Auditで確認します。

## 継続台帳

台帳はネイティブGoogleスプレッドシート正本へ直接アクセスします。旧Excel版やGitHub旧スナップショットを最新と推定しません。

更新時は必要範囲だけを書き換え、数式・書式・既存集計を維持します。画像、日次CSV、検証report、ログ等の運用成果物は引き続きcommitしません。

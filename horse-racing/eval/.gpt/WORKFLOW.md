# Eval GPT workflow

## 0. GitHub routing policy (2026-09-10)

このプロジェクトでは、処理開始時に「本当にGitHub Actions環境が必要か」を先に判定する。Issue駆動Actionsを一律の標準経路にはしない。

経路は次の4系統とする。

- **A: Read / Audit** — repository/file/commit/issue/workflow/result/artifact metadata/SHA/diff/main状態の確認。GitHub read/search/fetchを直接使い、Issueを作らない。
- **B: Git Change** — source/test/docs/config/workflow等のUTF-8テキスト変更。最新main、対象path、現内容を確認後、GitHub contents API相当のdirect create/update/deleteでmainへ直接commitする。`[gpt-git-update]` は標準経路としない。
- **C: Pure Deterministic Execution** — GitHub mainの既存Python/ロジックを、入力がChat/ローカルにあり、Secrets・特別なActions環境・長時間/大容量処理・immutable artifact監査が不要な場合にChat/ローカルで直接実行する。
- **D: Actions-Native Execution** — Secrets、Actions artifact chain、長時間/大容量、runner固有依存、immutable freeze、監査run、scheduled/third-party reproducibility等が必要な処理。既存Issue/Actions経路を維持する。

A/B/Cで完結できる処理のためだけにIssueを作らない。Dを選んだ場合のみ、ルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を適用する。

## 1. 共通preflight

1. GitHub `main` の最新状態を確認する。
2. `horse-racing/eval/README.md`、`.gpt/CONTEXT.md`、本ファイル、対象moduleのdocs/Pythonを確認する。
3. 既存の入出力契約と業務仕様を維持する。
4. 実行経路A/B/C/Dを決める。DでなければIssueを作らない。

## 2. このスレッドの標準: Chatへ直接渡されたEval画像 -> 完成CSV

ユーザーがEval表画像または画像ZIPをChatへ直接渡し、「CSV化」「完成CSV」等を依頼した場合は次を標準とする。

```text
ユーザー画像
  -> C: GitHub mainのEval OCRロジックをChat/ローカルで実行
  -> OCR validationを通過した5列CSV
  -> D: [EVAL_PACI_ENRICH_REQUEST] Issue
  -> ActionsでJRDB PACIをSecrets認証取得
  -> enrich_eval_csv_with_paci.py
  -> 完成CSV + audit artifact
  -> A: Issue RESULT / run / artifactを直接確認・回収
  -> ユーザーへ返却
```

### 2.1 OCR工程 = C: Pure Deterministic Execution

- 対象: `src/extract_eval_table.py` / `src/eval_ocr/`
- 入力画像はChat/ローカルに存在するものを使用する。
- 直接アップロードされた画像をGitHubへ永続化しない。
- 通常の中間CSV契約は `date,venue,race_no,horse_no,eval` の5列。
- 会場/R/馬番構造、Eval範囲、重複、色順位、tie、manual-review要求等の既存validationを通す。
- OCR validationがerrorの場合はPACI工程へ進めない。推測補正で通過扱いにしない。
- OCRのみを明示された場合は5列CSVで停止してよい。

OCRはSecretsを使わず、ユーザー入力が手元にあり、通常開催規模ならローカル実行可能なため、Issue/Actionsを標準としない。

### 2.2 PACI取得・enrichment = D: Actions-Native Execution

`[EVAL_PACI_ENRICH_REQUEST]` と `.github/workflows/eval_paci_enrich_chat.yml` は維持する。

理由:

- PACI取得に `JRDB_USER` / `JRDB_PASSWORD` Secretsが必要。
- JRDB有料原データをChatへ認証情報付きで直接取得させない。
- PACI取得、結合、audit、artifactを同一run revisionへ固定して追跡できる。
- 完成CSVの監査runとして `run_id` / artifact / summaryを残す価値がある。

Issue本文は5列OCR CSVをgzip+Base64化したpayloadとし、通常 `fail_on_unmatched=true` を使用する。

成功条件:

- `fetch_exit_code == 0`
- `enrich_exit_code == 0`
- `collect_exit_code == 0`
- `joined_horses == input_rows`
- `unmatched_horses == 0`
- `duplicate_keys == 0`
- `race_headcount_mismatches` は必ず監査し、0でなければ明示する。

PACI ZIPをユーザーへ再添付依頼しない。

## 3. Eval表メディア取得

### 3.1 既に画像がChatへ渡されている場合

画像取得工程は不要。2章のOCRから開始する。

### 3.2 X投稿から新規取得する場合 = 原則 D

`src/master_eval_media_collector.py` と `.github/workflows/eval_media_chat.yml` の `[EVAL_MEDIA_REQUEST]` を維持する。

Secrets必須ではないが、外部投稿の取得結果・metadata・media・validationを同一runのartifactとして残すこと自体が取得時点の監査証跡になるため、通常の収集運用はActions-Nativeとする。

ただし、単発のread確認だけで済み、Chat側で対象画像を既に直接取得できており、immutableな取得artifactが不要ならIssueを追加で作らない。

Actionsを使う場合は `EVAL_MEDIA_RESULT` の `fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を確認し、run/artifactをA: Read/Auditで回収する。

## 4. 既存media artifact -> OCR

従来の `[EVAL_OCR_REQUEST]` / `.github/workflows/eval_ocr_chat.yml` は互換・監査用に残すが、標準経路ではない。

通常は:

1. A: upstream `EVAL_MEDIA_RESULT` とrun/artifactを直接確認する。
2. artifactを直接回収でき、規模が通常範囲ならChat/ローカルへ展開する。
3. C: GitHub mainのOCRロジックを直接実行する。

次の場合だけ `[EVAL_OCR_REQUEST]` をDとして使用する。

- artifact chainをGitHub内だけで連結し続ける必要がある。
- immutable OCR audit runを明示的に残したい。
- 対象画像が多く、Chat/ローカル実行に不向き。
- runner側のTesseract環境固定が再現性要件になっている。

## 5. JRA結果取得

`src/fetch_jra_daily_results.py` + `src/validate_jra_results.py` は、Secretsを必要としないためActions専用処理とはみなさない。

- Chat/ローカル環境から必要な外部アクセスが可能で、通常規模かつimmutable runが不要なら C: Pure Deterministic Execution。
- Chat/ローカルから外部取得できない、長期/大量取得、再現可能な取得run・artifactを残す必要がある場合は D: `[JRA_RESULTS_REQUEST]` / `.github/workflows/jra_results_chat.yml`。

Dを使う場合は `fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を成功条件とする。

出走頭数は取消・競走除外前の枠順確定時頭数を維持する。

## 6. GitHub Read / Audit とGit変更

repository/file/commit/issue/workflow/run/result/SHA/diffの確認はAとして直接行い、確認専用Issueは作成しない。

Python、Markdown、JSON、YAML、tests、workflow等のUTF-8テキスト変更はBとして直接GitHubへ反映する。変更前に必ず:

```text
latest main -> path存在確認 -> current content -> 必要差分
```

を確認する。変更後はcommit SHAと必要なCI/差分をAで確認する。

`[gpt-git-update]` は互換fallbackとして残るが、本プロジェクトの標準更新経路ではない。

## 7. 継続台帳

継続台帳の正本はネイティブGoogleスプレッドシート `Eval表集計・検証`（Spreadsheet ID `1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0`）。

- 参照・更新はGoogle Drive / Google Sheetsのnative操作を使用する。
- 旧Drive Excel版 / GitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` は移行前スナップショット。
- 旧Gitバイナリread/updateを台帳同期目的に使わない。
- 更新時は必要範囲だけ変更し、数式・書式・既存集計を維持する。

Eval `全馬データ` へJRDB SED結果を取り込む場合は `docs/README_jrdb_horse_results_import.md` を標準手順とし、外部Raw取得の認証・大量処理・監査要件に応じてC/Dを判定する。

## 8. Git管理対象外

Eval画像、OCR途中成果物、日次CSV、PACI Raw、検証レポート、実行ログ等の運用成果物は通常commitしない。PythonやWorkflowを変更した場合は対応README/docs/testsも必要に応じて同時更新する。

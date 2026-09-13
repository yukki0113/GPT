# Eval GPT workflow

## 0. GitHub routing policy (2026-09-10)

このプロジェクトでは、処理開始時に「本当にGitHub Actions環境が必要か」を先に判定する。Issue駆動Actionsを一律の標準経路にはしない。

経路は次の4系統とする。

- **A: Read / Audit** — repository/file/commit/issue/workflow/result/artifact metadata/SHA/diff/main状態の確認。GitHub read/search/fetchを直接使い、Issueを作らない。
- **B: Git Change** — source/test/docs/config/workflow等のUTF-8テキスト変更。最新main、対象path、現内容を確認後、GitHub contents API相当のdirect create/update/deleteでmainへ直接commitする。`[gpt-git-update]` は標準経路としない。
- **C: Pure Deterministic Execution** — GitHub mainの既存Python/ロジックを、入力がChat/ローカルにあり、Secrets・特別なActions環境・長時間/大容量処理・immutable artifact監査が不要な場合にChat/ローカルで直接実行する。
- **D: Actions-Native Execution** — Secrets、Actions artifact chain、長時間/大容量、runner固有依存、immutable freeze、監査run、scheduled/third-party reproducibility等が必要な処理。既存Issue/Actions経路を維持する。

A/B/Cで完結できる処理のためだけにIssueを作らない。Dを選んだ場合のみ、ルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を適用する。

## 1. 新規スレッド / 共通preflight

会話履歴が無い新規スレッドでも復元できるよう、次を順に確認する。

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. GitHub `main` の最新状態
3. `horse-racing/eval/README.md`
4. `.gpt/CONTEXT.md`
5. 本 `.gpt/WORKFLOW.md`
6. `.gpt/HANDOFF.md`
7. 対象moduleのdocs / source / tests / workflow
8. OCRなら `docs/OCR_Validation_Contract.md`
9. Phase2なら current contracts:
   - `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md`
   - `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md`
   - `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md`
10. PWAコメントなら:
   - `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md`
   - `docs/Eval_PWA_Submission_Daily_Operation_v0_1.md`

そのうえで既存入出力仕様と業務仕様を維持し、実行経路A/B/C/Dを決める。DでなければIssueを作らない。

過去スレッドの記憶だけでmodule名・条件・run IDを補完しない。GitHub正本または外部正本を再確認する。

version付きcontractと実source `VERSION` / schemaが食い違う場合は、古いcontractへ実装を推測で合わせず、source/tests/docsを監査してcurrent contractを更新する。

## 2. このスレッドの標準: Chatへ直接渡されたEval画像 -> 完成CSV -> PWA提出CSV

ユーザーがEval表画像または画像ZIPをChatへ直接渡し、「CSV化」「完成CSV」等を依頼した場合は次を標準とする。PWA連携を行う通常運用では完成CSVの後にPWA提出CSVまで派生生成する。

```text
ユーザー画像
  -> A: latest main / contract確認
  -> C: GitHub mainのEval OCRロジックをChat/ローカルで実行
  -> OCR validationを通過した5列CSV
  -> D: [EVAL_PACI_ENRICH_REQUEST] Issue
  -> ActionsでJRDB PACIをSecrets認証取得
  -> enrich_eval_csv_with_paci.py
  -> 完成CSV + audit artifact
  -> A: Issue RESULT / run / artifactを直接確認・回収
  -> C: Eval研究側で注目馬analysis overlayを作成
  -> C: build_eval_pwa_submission.py
  -> YYYYMMDD_Eval_PWA提出CSV_v0_1.csv + audit
  -> 簡潔な当日分析サマリ
  -> ユーザーへ返却
```

OCRのみ、または完成CSVのみを明示された場合はその段階で停止してよい。

### 2.1 OCR工程 = C: Pure Deterministic Execution

- 対象: `src/extract_eval_table.py` / `src/eval_ocr/`
- 入力画像はChat/ローカルに存在するものを使用する。
- 直接アップロードされた画像をGitHubへ永続化しない。
- 通常の中間CSV契約は `date,venue,race_no,horse_no,eval` の5列。
- R番号はパネル位置、馬番は行位置。馬名文字列はOCRしない。
- 会場/R/馬番構造、Eval範囲、重複、色順位、tie、manual-review要求等の既存validationを通す。
- 色順位は `red -> blue -> orange -> green -> yellow` の画像凡例固定。OCR値から推定しない。
- `9x` 等の2/9先頭桁疑義、着色1桁、色順位矛盾等は独立再読する。機械置換しない。
- `requires_review` が1件でも残ればformal completion pathを停止する。
- OCR validationがerrorの場合はPACI工程へ進めない。推測補正で通過扱いにしない。
- OCRのみを明示された場合は5列CSVで停止してよい。

OCR release gateは `docs/OCR_Validation_Contract.md` を正本とする。PACI join成功をOCR品質の代用にしてはいけない。

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

通常ユーザー返却名は `YYYYMMDD_Eval_完成CSV.csv`。OCR 5列CSV / OCR validation / PACI auditは監査用補助成果物として併せて保持できる。

### 2.3 PWA提出CSV = C: Pure Deterministic Execution

完成CSVの既存列は変更せず、研究側analysis overlayを `src/build_eval_pwa_submission.py` でexact mergeする。

責務分離:

- 研究側: 注目馬選定、condition code、WATCH/MATCH、title/comment、as-of
- builder: canonical key exact merge、6列付与、NONE補完、整合validation、audit
- Newspaper/PWA: contractどおり透過格納・表示。条件再判定は禁止

正本:

- `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md`
- `docs/Eval_PWA_Submission_Daily_Operation_v0_1.md`

標準出力名:

```text
YYYYMMDD_Eval_PWA提出CSV_v0_1.csv
```

最低audit:

```text
source_rows == output_rows
source canonical keys == output canonical keys
existing source columns unchanged
unknown analysis key == 0
NONE -> comment blank
WATCH/MATCH -> codes/title/comment/version/asof present
```

Eval順位条件で同値tie等の定義が完成CSVだけから一意に再現できない場合、馬番順等の便宜的tie-breakを正式条件として採用しない。current research contract / ledger定義を確認し、未解決ならcondition codeを保留する。

PWA提出CSV返却時は、CSVリンクだけで終わらせず次を短くスレッドへ併記する。

- 当日最高Eval、必要なら上位3～5頭
- WATCH/MATCH・主要code件数
- 目立つ馬3～5頭程度
- `Eval97` 等の極端値、またはデータ警告

全候補の詳細説明は通常PWAモーダルへ任せる。

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

`.github/workflows/eval_image_enrich_chat.yml` / `[EVAL_IMAGE_ENRICH_REQUEST]` は旧combined compatibility経路。Chatへ画像が直接添付される通常運用では使用しない。現在の標準はC: direct OCR + D: PACI enrichment。

## 5. Phase2 research

Phase2事前特徴の固定長parseはJRDB common parser/adapterへ委譲し、Eval側でBYTE offsetを再定義しない。

### 5.1 Pre-race components

- `src/build_phase2_jrdb_kyi_features.py` — KYI事前特徴。current contractは `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md`。current-race結果を読まない。
- `src/build_phase2_jrdb_training_features.py` — KYI identity setへCHA/CYBをLEFT JOIN。contractは `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md`。CHA/CYB欠損馬をrunner setから落とさない。
- `src/build_phase2_jrdb_previous_features.py` — KYI `previous[0].result_key` とPACI ZED `result_key` を完全一致。contractは `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md`。fallback禁止。
- `src/build_phase2_jrdb_feature_bundle.py` — 3componentを `race_horse_key` で1対1結合し、identity/source/version不一致をerrorにする。blank/Noneは同一missingとして正規化する。

current-race SED、確定着順、確定人気・オッズ、払戻等をForward事前特徴へ混入させない。

KYI `training_index`、CHA `cha_workout_index`、CYB `cyb_workout_index` は別概念。値が一致する前提にせず、それぞれ保持する。

### 5.2 Post-race layer

- `src/backfill_phase2_sed.py` — SED結果時点layer。
- `docs/Phase2_SED_Backfill_20260908.md` — 既存backfill監査。

事前特徴と結果layerを混在させない。

### 5.3 Research / PWA boundary

Discovery結果を同一標本のまま正式購入条件へ昇格させない。

PWA analysis列・WATCH/MATCH・analysis code/commentの責務境界は `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md` を正本とする。日次生成・監査・スレッド要約は `docs/Eval_PWA_Submission_Daily_Operation_v0_1.md` を正本とする。PWA/Newspaper側で研究条件を再実装しない。

## 6. JRA結果取得

`src/fetch_jra_daily_results.py` + `src/validate_jra_results.py` は、Secretsを必要としないためActions専用処理とはみなさない。

- Chat/ローカル環境から必要な外部アクセスが可能で、通常規模かつimmutable runが不要なら C: Pure Deterministic Execution。
- Chat/ローカルから外部取得できない、長期/大量取得、再現可能な取得run・artifactを残す必要がある場合は D: `[JRA_RESULTS_REQUEST]` / `.github/workflows/jra_results_chat.yml`。

Dを使う場合は `fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を成功条件とする。

出走頭数は取消・競走除外前の枠順確定時頭数を維持する。

## 7. GitHub Read / Audit とGit変更

repository/file/commit/issue/workflow/run/result/SHA/diffの確認はAとして直接行い、確認専用Issueは作成しない。

Python、Markdown、JSON、YAML、tests、workflow等のUTF-8テキスト変更はBとして直接GitHubへ反映する。変更前に必ず:

```text
latest main -> path存在確認 -> current content -> 必要差分
```

を確認する。変更後はcommit SHAと必要なCI/差分をAで確認する。

`[gpt-git-update]` は互換fallbackとして残るが、本プロジェクトの標準更新経路ではない。

## 8. 継続台帳

継続台帳の正本はネイティブGoogleスプレッドシート `Eval表集計・検証`（Spreadsheet ID `1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0`）。

- 参照・更新はGoogle Drive / Google Sheetsのnative操作を使用する。
- 旧Drive Excel版 / GitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` は移行前スナップショット。
- 旧Gitバイナリread/updateを台帳同期目的に使わない。
- 更新時は必要範囲だけ変更し、数式・書式・既存集計を維持する。

Eval `全馬データ` へJRDB SED結果を取り込む場合は `docs/README_jrdb_horse_results_import.md` を標準手順とし、外部Raw取得の認証・大量処理・監査要件に応じてC/Dを判定する。

Canonical Keyを文字列化する場合は `開催日|場|R|馬番` の区切り付き形式を使用し、可変桁の単純連結をしない。

## 9. スレッド引っ越し / interruption

通常の週次作業は、latest main + `.gpt/HANDOFF.md` + 当日画像または完成CSVがあれば新スレッドで再開可能とする。過去チャット全文を前提にしない。

途中状態を引き継ぐ場合は、最低限次を圧縮して残す。

```text
対象日
入力画像/ZIP
OCR実行済みか
OCR validation status
5列CSV reference
PACI Issue/request_id
PACI run_id/artifact_name
完成CSV生成済みか
完成CSV reference
PWA analysis contract/version
analysis as-of
analysis overlay生成済みか
PWA提出CSV生成済みか
highlighted_rows / code_counts
未解決tie/rank review
スレッド簡潔サマリ返却済みか
未解決manual review/error
Git source commit/SHA
```

不明なrun/artifact/statusを推測しない。GitHubからA: Read/Auditで再確認する。

## 10. Git管理対象外

Eval画像、OCR途中成果物、日次CSV、PACI Raw、検証レポート、実行ログ等の運用成果物は通常commitしない。PythonやWorkflowを変更した場合は対応README/docs/testsも必要に応じて同時更新する。

思想、標準経路、canonical key、release gate、主要module責務が変わった場合はREADME / CONTEXT / WORKFLOW / HANDOFFの整合性を同時に監査する。

# Eval表活用

中央競馬のEval表取得・OCR・検証・JRDB事前情報付与、Phase2研究、結果取込を支援するツール群です。

## Source of truth

GitHub `yukki0113/GPT` の `main` ブランチ配下 `horse-racing/eval/` をPython・README・作業手順の正本とします。

画像、OCR途中成果物、日次CSV、ログ、JRDB Raw等の運用成果物は通常Git管理対象外です。

継続台帳は **ネイティブGoogleスプレッドシート `Eval表集計・検証`** を正本とします。

- Spreadsheet ID: `1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0`
- Chat / WorkからはGoogle Drive / Google Sheetsのnative操作で直接参照・更新する。
- 旧Google Drive Excel版およびGitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` は移行前スナップショットであり、最新台帳として使用しない。

## 新しいChat / Workスレッドのbootstrap

会話履歴へ依存せず再開できるよう、開始時は次の順で確認します。

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. 本 `README.md`
3. `.gpt/CONTEXT.md`
4. `.gpt/WORKFLOW.md`
5. `.gpt/HANDOFF.md`
6. 対象処理の `docs/` と実source/tests/workflow

`.gpt/HANDOFF.md` に、プロジェクトの思想、weekly画像→完成CSVのrelease gate、主要module map、Phase2のリーケージ境界、スレッド引っ越し時の最小引継ぎをまとめています。

## Core principles

- **PACI join success != OCR correctness.** PACIはidentity/key整合を検証するがEval OCR値の正しさは保証しない。
- 正式完成条件は `OCR validation == ok AND PACI join validation == success`。
- 順位色は画像凡例の固定順 `red -> blue -> orange -> green -> yellow` を正本とし、OCR数値から色順位を推定しない。
- 0905で確認した `2` / `9` 先頭桁誤読等は独立再読し、根拠が弱ければmanual reviewでfail-closedにする。
- OCR中間CSVは `date,venue,race_no,horse_no,eval` の5列。馬名文字列はOCRせず、JRDB PACIからcanonical keyで付与する。
- Phase2の事前特徴と結果時点データを分離し、current-race SED・確定結果等をForward事前特徴へ混入させない。
- JRDB固定長BYTE位置はJRDB common parser/adapterを正本とし、Eval側へ局所複製しない。
- Discoveryで見つかった特徴を同一標本のまま正式購入条件へ昇格させない。

詳細は `.gpt/HANDOFF.md`、`docs/OCR_Validation_Contract.md`、各Phase2 contractを参照してください。

## GitHub運用ルーティング — 2026-09-10

Issue / GitHub Actionsを一律の標準経路にはしません。処理開始時に「GitHub Actions環境が本当に必要か」を判定し、次の4系統から選びます。

| 経路 | 用途 | Evalでの代表例 |
|---|---|---|
| A: Read / Audit | GitHub上の状態確認 | main、file、commit、Issue RESULT、run、artifact metadata、SHA、diff確認 |
| B: Git Change | UTF-8テキスト変更 | Python、tests、README、`.gpt/`、workflowのdirect update/create/delete |
| C: Pure Deterministic Execution | Secrets等が不要な既存ロジックの直接実行 | Chatへ渡されたEval画像のOCR/validation、固定入力の変換・監査 |
| D: Actions-Native Execution | Secrets、artifact chain、長時間/大容量、immutable freeze、監査run等 | JRDB PACI認証取得+enrichment、取得時点をartifact固定するEval media collection |

A/B/Cで完結する処理のためだけにIssueを作成しません。DでIssue/Actionsを使用するときだけ、ルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を適用します。

## Current tools

### Weekly / OCR

- `src/master_eval_media_collector.py` — X上のEval表メディア収集
- `src/extract_eval_table.py` — Eval表画像を5列CSVへ変換するOCR親CLI
- `src/eval_ocr/layout_detector.py` — 会場/Rパネル・表構造検出
- `src/eval_ocr/japanese_ocr.py` — 会場ヘッダーOCR
- `src/eval_ocr/numeric_ocr.py` — Eval数値OCR、digit repair、独立再読、cell audit
- `src/eval_ocr/color_detector.py` — Eval順位色分類
- `src/eval_ocr/pipeline.py` — OCR/color統合と色矛盾による再読
- `src/eval_ocr/validator.py` — 構造・値域・キー・色順位・manual reviewのrelease gate
- `src/fetch_jra_daily_results.py` — JRA日次結果・払戻取得
- `src/validate_jra_results.py` — JRA結果CSVの機械検証

### JRDB integration

- `../jrdb/src/fetch_jrdb_paci.py` — 認証付きPACI取得
- `../jrdb/src/enrich_eval_csv_with_paci.py` — Eval OCR 5列CSVへJRDB PACI事前情報を付与
- `../jrdb/src/export_jrdb_eval_horse_results.py` — JRDB SED Raw → `全馬データ` 結果用1頭1行CSV + audit JSON

### Phase2 pre-race research

- `src/build_phase2_jrdb_kyi_features.py` — KYI事前特徴
- `src/build_phase2_jrdb_training_features.py` — CHA/CYB調教・仕上特徴
- `src/build_phase2_jrdb_previous_features.py` — KYI previous result key -> PACI ZED exact-link前走特徴
- `src/build_phase2_jrdb_feature_bundle.py` — 上記3componentを1頭1行へ統合

### Post-race / research backfill

- `src/backfill_phase2_sed.py` — Phase2へSED結果時点情報をbackfill

各ツールの詳細は `docs/`、責務一覧は `.gpt/HANDOFF.md` を参照してください。

## このスレッドの標準: Eval画像 -> 完成CSV

ユーザーがChatへEval表画像または画像ZIPを直接渡して「完成CSV」「CSV化」を依頼した場合の標準フローです。

```text
ユーザー画像
  -> A: latest main / contract確認
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
- `date + venue + race_no + horse_no` の重複、1〜12R構造、Eval 0〜100等を検証
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

`.github/workflows/eval_image_enrich_chat.yml` / `[EVAL_IMAGE_ENRICH_REQUEST]` は旧combined compatibility経路です。現在のChat直接画像運用の標準は **C: direct OCR + D: PACI enrichment** であり、画像Base64 chunkをIssueへ搬送するcombined workflowを通常使用しません。

## Phase2 research boundary

Phase2事前研究ではPACI由来の開催前情報を利用します。

- KYI: 当日リスク・適性・休養・調教判断等
- CHA/CYB: 本追切・調教分析・仕上過程
- ZED: KYIが明示する前走result keyをexact-linkした既走履歴

current-race SED、確定着順・人気・オッズ・払戻等は事前特徴に使用しません。結果backfillは別レイヤーです。

現行contractは以下を正本とします。

- `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md`
- `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md`
- `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md`

研究条件やPWA analysis codeの定義は `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md` 等の契約へ置き、READMEへ複製して二重管理しません。

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

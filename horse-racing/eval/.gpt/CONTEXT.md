# Eval project context

## Status

Active。Eval表の画像取得、OCR/検証、JRDB事前情報付与、Phase2研究、結果取得、台帳更新を支援する領域です。

スレッド引っ越し用のdurable bootstrapは `.gpt/HANDOFF.md` を参照してください。過去チャット全文を前提にせず、latest main + project docs + 対象入力から再開できる状態を維持します。

## Source of truth

Python、README、作業手順、依存関係、GitHub Actions WorkflowはGitHub `yukki0113/GPT` の `main` を正本とします。

Eval画像、OCR途中成果物、日次取得CSV、検証レポート、ログ、JRDB Raw等の運用成果物は通常Git外を正本とします。

継続台帳はネイティブGoogleスプレッドシート `Eval表集計・検証` を正本とします。

- Spreadsheet ID: `1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0`
- Chat / WorkではGoogle Drive / Google Sheetsのnative操作で直接参照・更新する。
- 旧Google Drive Excel版とGitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` は移行前スナップショットであり、最新台帳として扱わない。

## Durable principles

1. PACI joinはidentity/key整合を示すだけで、Eval OCR値の正しさを保証しない。
2. 正式完成条件は `OCR validation == ok AND PACI join validation == success`。
3. Eval順位色は画像凡例の固定順 `red -> blue -> orange -> green -> yellow`。OCR値から推定しない。
4. 0905で確認した2/9先頭桁誤読等は独立再読し、根拠不足ならmanual reviewでfail-closed。
5. OCR中間契約は `date,venue,race_no,horse_no,eval`。馬名文字列はOCRせずPACIから付与する。
6. Phase2事前特徴へcurrent-race結果時点データを混ぜない。結果backfillは別layer。
7. JRDB固定長BYTE位置はJRDB common parser / adapterを正本とし、Eval側へ複製しない。
8. Discovery特徴を同一標本のまま正式Forward条件へ昇格させない。
9. PWA/Newspaperは研究条件を再実装せず、Eval側contractが判定・analysis commentを所有する。

OCR詳細は `docs/OCR_Validation_Contract.md` を正本とします。Phase2のcurrent contractsは:

- `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md`
- `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md`
- `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md`

PWA責務境界は `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md` を正本とします。

## GitHub execution routing — 2026-09-10

Issue駆動Actionsを一律の標準経路にはしない。処理開始時に次の4系統を判定する。

- A: Read / Audit — GitHubのfile/commit/issue/run/artifact/SHA/diff確認。Issue不要。
- B: Git Change — UTF-8テキストのsource/test/docs/config/workflow変更。最新main/current content確認後にdirect create/update/deleteでmainへcommitする。
- C: Pure Deterministic Execution — 入力が手元にありSecretsや特別なrunner、長時間/大容量、immutable auditが不要な既存ロジックをChat/ローカルで直接実行する。
- D: Actions-Native Execution — Secrets、artifact chain、長時間/大容量、runner固有依存、immutable freeze、監査run等が必要な処理。既存Issue/Actionsを維持する。

DでIssueを作る場合のみ、ルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を適用する。

## Eval表OCR

本体は `src/extract_eval_table.py` と `src/eval_ocr/`。通常出力CSVは `date,venue,race_no,horse_no,eval` の5列。

馬名セル画像は行存在判定に使用するが馬名文字列のOCRは行わない。会場名ヘッダーOCR、Eval数値OCR、色付き上位セル・同色tie・固定色順位とEval大小のvalidationを維持する。

`numeric_ocr.py` はstack OCR、digit component repair、独立再読、cell auditを担当する。`pipeline.py` は色矛盾を独立情報として二段階再読へ使い、`validator.py` は構造・値域・キー・色順位・manual reviewをfail-closed gateとして評価する。

正式馬名・レース属性・馬属性は後段のJRDB PACI enrichmentが `date + venue + race_no + horse_no` をキーに付与する。

ChatへユーザーがEval表画像を直接渡す通常運用では、OCRはC: Pure Deterministic Executionとし、GitHub mainの正本ロジックをChat/ローカルで実行する。OCR validationがerrorならPACI enrichmentへ進めない。

既存 `[EVAL_OCR_REQUEST]` / `.github/workflows/eval_ocr_chat.yml` は、GitHub内artifact chain、immutable OCR audit、多数画像、runner側Tesseract環境固定が必要な場合のD経路として残す。

旧 `.github/workflows/eval_image_enrich_chat.yml` / `[EVAL_IMAGE_ENRICH_REQUEST]` はcombined compatibility経路であり、通常のChat直接画像処理の第一選択ではない。

## Chat画像 -> 完成CSV

通常の最終成果物は5列OCR CSVではなく、JRDB PACI事前情報まで付与した完成CSVとする。OCRのみを明示された場合だけ5列で停止してよい。

標準フロー:

```text
ユーザー画像
  -> A: latest main / contract確認
  -> C: Chat/ローカルでGitHub mainのOCRロジックを使用
  -> OCR validation PASS
  -> 5列OCR CSV
  -> D: [EVAL_PACI_ENRICH_REQUEST]
  -> Actions Secretsで対象日PACIを取得
  -> enrich_eval_csv_with_paci.py
  -> 完成CSV + audit artifact
  -> A: RESULT/run/artifactを直接確認・回収
```

直接アップロードされた画像はGitHubへ永続化しない。GitHubへ渡すのはOCR後の5列CSVを圧縮・Base64化したpayloadのみ。

PACI取得には `JRDB_USER` / `JRDB_PASSWORD` Secretsが必要なため、`.github/workflows/eval_paci_enrich_chat.yml` はD: Actions-Native Executionとして維持する。

通常成功条件は `joined_horses == input_rows`、`unmatched_horses == 0`、`duplicate_keys == 0`。`race_headcount_mismatches` は必ず監査する。

## Eval表画像取得

本体は `src/master_eval_media_collector.py`。

ユーザーが画像を直接添付済みなら画像取得工程は不要。

X投稿から新規に取得し、取得時点のmetadata/media/validationを同一runのartifactへ固定する運用では、`.github/workflows/eval_media_chat.yml` / `[EVAL_MEDIA_REQUEST]` をDとして維持する。これは外部投稿の取得物をimmutableな監査証跡として扱うため。

単発のRead確認で既に画像を直接取得できておりartifact固定が不要なら、追加Issueを作らない。

## Phase2 research

事前特徴module:

- `src/build_phase2_jrdb_kyi_features.py` — current contract `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md`
- `src/build_phase2_jrdb_training_features.py` — current contract `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md`
- `src/build_phase2_jrdb_previous_features.py` — current contract `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md`
- `src/build_phase2_jrdb_feature_bundle.py`

KYIをrunner identityの基準とし、CHA/CYBはLEFT JOIN、前走はKYI result key -> PACI ZED exact-link。推測fallbackを行わない。

current-race SED・確定結果は事前特徴へ使用しない。`src/backfill_phase2_sed.py` は結果時点layerとして分離する。

KYI `training_index`、CHA `cha_workout_index`、CYB `cyb_workout_index` は意味が異なるため統合しない。

## JRA結果取得

本体は `src/fetch_jra_daily_results.py`、検証は `src/validate_jra_results.py`。

Secrets不要なのでActions専用ではない。外部アクセス可能な環境で通常規模・監査run不要ならCで直接実行できる。

Chat/ローカルから取得先へ到達できない、長期/大量取得、または取得run/artifactの固定が必要な場合は `.github/workflows/jra_results_chat.yml` / `[JRA_RESULTS_REQUEST]` をDとして使用する。

出走頭数は取消・競走除外前の枠順確定時頭数を維持する。

## Git changes / audits

GitHub上の確認作業はAとして直接read/search/fetchする。確認専用Issueは作らない。

Python、Markdown、JSON、YAML、tests、workflow等のUTF-8テキスト変更はBとしてdirect create/update/deleteでmainへ反映する。`[gpt-git-update]` は標準経路ではない。

変更後のcommit/SHA/CI確認はAで行う。

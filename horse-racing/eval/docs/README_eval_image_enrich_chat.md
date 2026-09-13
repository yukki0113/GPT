# Eval image -> PACI enriched CSV (Chat)

## Status

**Compatibility / legacy combined path.**

2026-09-10以降、ChatへEval表画像が直接渡される通常運用では、このcombined Issue workflowを標準経路にしません。

現在の正本フローは `horse-racing/eval/README.md`、`.gpt/WORKFLOW.md`、`.gpt/HANDOFF.md` を参照してください。

```text
Eval表画像
  -> C: Chat/ローカルでGitHub mainのEval OCRを直接実行
  -> OCR validation PASS
  -> 5列CSV
  -> D: [EVAL_PACI_ENRICH_REQUEST]
  -> Actions Secretsで対象日PACI取得
  -> JRDB PACI enrichment
  -> 完成CSV + audit artifact
```

OCRにSecretsやActions固有環境は不要なため、画像Base64搬送のためだけにIssueを起こしません。一方、PACI取得は `JRDB_USER` / `JRDB_PASSWORD` Secretsを必要とするためActions-Nativeを維持します。

## Release gate

PACI joinの成功はOCR品質の証明ではありません。正式完成条件は次です。

```text
ocr_validation_status == ok
AND
paci_join_validation_status == success
```

OCRの固定色順位、2/9再読、manual review等は `docs/OCR_Validation_Contract.md` を正本とします。

## Current standard PACI path

Workflow:

```text
.github/workflows/eval_paci_enrich_chat.yml
```

Issue:

```text
[EVAL_PACI_ENRICH_REQUEST] <request_id>
```

Issue本文はOCR済み5列CSVをgzip+Base64化して渡します。

```json
{
  "eval_csv_gzip_b64": "<gzip+Base64 five-column CSV>",
  "output_name": "eval_YYYYMMDD_enriched.csv",
  "fail_on_unmatched": true
}
```

通常成功条件:

```text
fetch_exit_code == 0
enrich_exit_code == 0
collect_exit_code == 0
joined_horses == input_rows
unmatched_horses == 0
duplicate_keys == 0
```

`race_headcount_mismatches` は必ず監査します。

## Legacy combined workflow

次の資産は互換性・非常時のためrepositoryに残っています。

```text
.github/workflows/eval_image_enrich_chat.yml
[EVAL_IMAGE_ENRICH_REQUEST]
```

旧方式は画像をBase64 chunkでIssueコメントへ搬送し、Actions内でOCRからPACI enrichmentまで連続実行します。

現在この経路を使うのは、たとえば次のようにcombined Actions run自体を明示的に監査証跡として必要とする場合に限ります。

- Chat/ローカルでOCR runtimeを用意できない
- 画像搬送からOCR/PACIまで1つのimmutable Actions runへ固定する要件がある
- runner側Tesseract環境そのものを再現性要件とする

単に「ユーザーがChatへ画像を添付して完成CSVが欲しい」という通常依頼では使用しません。

## Artifacts / Git policy

ユーザー画像、OCR途中CSV、完成CSV、validation JSON、PACI Raw、ログ等の日次成果物は通常Gitへcommitしません。

標準経路ではユーザー画像自体をGitHubへ永続化せず、PACI Issueへ渡すのはOCR済み5列CSV payloadのみです。

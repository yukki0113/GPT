# Eval image -> PACI enriched CSV (Chat)

日常開催でユーザーがEval表画像をChatへ直接渡す場合の標準経路です。

```text
Eval表画像
  -> Eval OCR 5列CSV
  -> 対象日PACIyymmdd.zip取得
  -> JRDB PACI enrichment
  -> 開催前完成CSV
```

GitHub Actions workflow: `.github/workflows/eval_image_enrich_chat.yml`

Issue title:

```text
[EVAL_IMAGE_ENRICH_REQUEST] <request_id>
```

Issue本文JSON:

```json
{
  "date": "2026-08-29",
  "image_ext": "jpg",
  "expected_venues": 3,
  "output_name": "eval_20260829_enriched.csv",
  "fail_on_unmatched": true
}
```

画像本体はGitへcommitせず、IssueコメントへBase64 chunkとして搬送します。
各chunkは次の形式です。

```text
EVAL_IMAGE_CHUNK 1/N
<base64>
```

全chunk登録後、次のコメントを追加するとworkflowを開始します。

```text
EVAL_IMAGE_PAYLOAD_READY
```

workflowはchunkを再構成し、Git正本の `horse-racing/eval/src/extract_eval_table.py` を実行します。OCR成功後、`horse-racing/jrdb/src/fetch_jrdb_paci.py` で対象日PACIを取得し、`horse-racing/jrdb/src/enrich_eval_csv_with_paci.py` で正式馬名・開催前JRDB情報を付与します。

成功条件はOCR、PACI取得、enrichment、artifact収集がすべてexit code 0であることです。通常運用では `fail_on_unmatched=true` とし、PACI未結合馬が1頭でもあれば失敗にします。

artifactには完成enriched CSV、OCR 5列CSV、OCR validation JSON、PACI enrichment audit JSON、ログを含めます。画像そのものはartifactへ含めません。

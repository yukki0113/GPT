# master_eval_media_collector

`@master_eval` のX/Twitter投稿に添付された画像を、投稿ID（status ID）単位で取得するためのcollectorです。

## 目的 / responsibility

このmoduleは「投稿IDから添付画像とmetadataを取得する」ところまでを担当します。

担当外:

- 対象日から投稿IDを探索すること
- 取得画像がEval表本体か注意事項/告知画像かを意味判定すること
- OCRやPACI enrichment

画像内容の選別は後工程で行います。

## 正本

- `horse-racing/eval/src/master_eval_media_collector.py`
- `horse-racing/eval/docs/README_master_eval_media_collector.md`
- `.github/workflows/eval_media_chat.yml`
- `.github/workflows/eval_media_manual.yml`

取得画像、metadata、validation report、ログ、最終ZIP等の日次成果物はGitへcommitしません。

GitHub実行経路はroot `.gpt/GITHUB_OPERATION_POLICY.md` と `horse-racing/eval/.gpt/WORKFLOW.md` を上位正本とします。

## 動作環境 / 取得経路

- Python 3
- 外部Python package不要
- Python標準libraryのみ

公開経路を順に試します。

1. FxTwitter public API
2. Twitter/X syndication endpoint

X公式画面HTMLの直接scrapeではありません。公開API/埋め込み経路は将来変更される可能性があります。

## 基本実行

```bash
python horse-racing/eval/src/master_eval_media_collector.py <post_id> [<post_id> ...] --out <output_dir>
```

例:

```bash
python horse-racing/eval/src/master_eval_media_collector.py \
  2078087318754259013 \
  2078437850614571317 \
  --out eval_20260718_19
```

出力:

```text
<output_dir>/
  <post_id>/
    metadata.json
    media_01.jpg
    media_02.jpg
    ...
```

`metadata.json` には取得経路と取得元API responseを保存します。mediaは可能なら元sizeを取得します。

終了code:

- `0`: 全取得成功
- `1`: metadata取得失敗、画像URL未検出、画像取得失敗等

## 実行経路

### D: Actions-Native Execution — 通常の監査付き収集

X投稿から新規取得し、**その取得時点のmetadata/media/validationをimmutable artifactとして残すことに価値がある通常収集**では `.github/workflows/eval_media_chat.yml` / `[EVAL_MEDIA_REQUEST]` を使います。

Secrets必須だからDなのではなく、外部投稿が後から変更・削除され得るため、取得時点をrun + artifactへ固定することが理由です。

役割分担:

1. Chatが対象日の `@master_eval` 投稿を探索し投稿IDを確定
2. preflight後に `[EVAL_MEDIA_REQUEST]` Issueを作成
3. Actionsがcollectorを実行
4. metadata/mediaの存在をvalidation
5. artifact化
6. `EVAL_MEDIA_RESULT` コメントを返却
7. ChatがartifactをA: Read/Auditで回収
8. Chatが画像を見てEval表本体のみ選別

Issue推奨形式:

```json
{
  "targets": [
    {"date": "2026-07-18", "post_id": "2078087318754259013"},
    {"date": "2026-07-19", "post_id": "2078437850614571317"}
  ]
}
```

Title:

```text
[EVAL_MEDIA_REQUEST] <request_id>
```

成功条件:

```text
fetch_exit_code == 0
validation_exit_code == 0
validation.validation_status == success
```

Actions validationは各投稿で次のみを確認します。

- `metadata.json` がある
- `media_XX.*` が1枚以上ある

**Eval表本体か注意事項画像かの内容分類はActions validationの責務ではありません。** media順も固定仕様ではありません。

### C: Pure Deterministic Execution — artifact固定が不要な単発取得

次をすべて満たす場合は、GitHub mainのcollectorをChat/ローカルで直接実行できます。

- 実行環境から公開取得経路へ到達可能
- 通常規模
- downstreamがActions artifact chainを要求しない
- 取得時点をimmutable GitHub artifactとして正式監査保存する要件がない

単に「GitHubにworkflowがある」ことを理由にIssueを作りません。

ただし後から同一取得物を再現・監査する必要が高い通常の過去画像収集はDを優先します。

### 画像が既にChatへ直接添付済みの場合

collector自体を使いません。画像取得工程をskipし、`src/extract_eval_table.py` のOCRへ進みます。

## Eval表運用での後工程

media取得後:

1. 画像を内容確認
2. Eval表本体だけを採用
3. 注意事項・説明・告知画像を除外
4. 必要なら日付名へ整理
5. OCRへ渡す、または画像取得依頼ならZIP化

画像取得のみの最終ZIP命名例:

```text
eval_YYYYMMDD_YYYYMMDD_Eval表画像.zip
```

## 予備経路

`.github/workflows/eval_media_manual.yml` はGitHub UIからのmanual `workflow_dispatch` 用です。

## 注意事項

- 投稿ID探索はcollectorの担当外。
- 投稿URL/IDをユーザーが指定した場合は探索を省略可能。
- X/FxTwitter/syndicationの仕様変更で取得不能になり得る。
- `media_01` をEval表と決め打ちしない。
- 日付とpost IDの対応はD経路ではIssue本文 / `resolved_request.json` に残す。
- workflow/sourceの仕様を変えた場合はREADME / WORKFLOW / HANDOFFの整合性も確認する。

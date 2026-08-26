# keibailukaブログ解析モジュール

## 目的

`keibailuka.blogspot.com` の「全レース中の強き不利馬達」を、Chatで毎週行っている定型解析用に機械取得・整形する。

ユーザー入力は原則として次の2点だけとする。

- 対象日 (`YYYY-MM-DD`)
- 開催場の表示順

個別記事URLは通常入力にしない。記事URL探索もモジュール側で行う。

## 正本

- Python: `horse-racing/eval/src/fetch_keibailuka_blog.py`
- Chat用Workflow: `.github/workflows/keibailuka_chat.yml`
- 依存: `horse-racing/eval/requirements.txt`

## CLI

```bash
python horse-racing/eval/src/fetch_keibailuka_blog.py \
  --date 2026-08-23 \
  --venues 新潟 中京 札幌 \
  --output-dir ./output_keibailuka_20260823
```

オプション:

- `--interval`: HTTPアクセス間隔。既定 `0.8` 秒。
- `--timeout`: 1リクエストのタイムアウト。既定 `20` 秒。

## URL探索

検索エンジンのインデックスには依存しない。

次の経路を順次利用する。

1. Blogger公開JSON feed
2. ブログトップ
3. 対象月アーカイブ
4. 前月アーカイブ（日付が月初の場合を考慮）
5. Bloggerブログ内検索

記事タイトル中の `YYYY/M/D`、開催場、`全レース中の強き不利馬達` を照合して対象記事を確定する。

個別記事取得は通常URLを先に試し、失敗時は `?m=1` のモバイル表示を予備経路とする。429/5xxは間隔を置いて再試行する。

## 解析ルール

記事本文から各場 `1R`〜`12R` を抽出し、次のルールを適用する。

- `該当無し` → 出力しない
- `勝負レース` または `note.com/keibailuka/n/` への有料導入 → 出力しない
- `🤡` → 馬名を `🤡` として出力する
- 🤡欄の「noteにスキボタンを押すと馬名表示」文言 → コメントから除去する
- 通常馬 → 見出し中の馬名と直下コメントを出力する
- 開催場は依頼で渡された順、各場内は1R〜12R順を維持する

ブログ本文の意味を変える要約はPythonでは行わない。コメントは空白・CTA等だけを正規化し、長文の軽い要約が必要な場合はChat側で行う。

## 検証

各場について次を必須条件とする。

- 対象記事が一意に見つかること
- 1R〜12Rが順番どおり12個存在すること
- 各Rが `included` または `excluded` に分類できること
- 馬名を推測しないこと。見出しから安全に取れない場合は `parse_error` とする
- `included + excluded = 12`

条件を満たさない場合、validationをfailureとして終了コード2を返す。部分取得を成功扱いしない。

## 出力

対象日が `2026-08-23` の場合:

- `keibailuka_20260823.json`
  - source URL
  - 全12Rの解析状態
  - 最終採用entries
- `keibailuka_20260823.tsv`
  - `場所 / R / 馬名 / コメント`
  - `該当無し` と有料導入を除外済み
- `validation_report.json`
- Workflow利用時は `resolved_request.json`、`run_status.txt` も付与

日次出力はGit管理しない。

## Chat標準経路

タイトル:

```text
[KEIBAILUKA_REQUEST] <request_id>
```

Issue本文:

```json
{
  "date": "2026-08-23",
  "venues": ["新潟", "中京", "札幌"]
}
```

`.github/workflows/keibailuka_chat.yml` がIssue作成を検知して実行する。

完了時は同じIssueへ `KEIBAILUKA_RESULT` コメントを返し、自動クローズする。結果コメントには以下を含む。

- `run_id`
- artifact名
- fetch/validation終了コード
- validation結果
- 発見した記事URL
- 採用entries
- そのまま使えるPlain text TSV

したがってChatは通常artifactを展開せず、Issueコメントだけで最終回答を組み立てられる。必要な場合だけartifactを回収する。

## 運用上の位置づけ

通常運用では、ユーザーに記事URL探索を依頼しない。

ユーザーからURLが提示された場合も、そのURLを恒常的な入力仕様には昇格させない。ブログ側の仕様変更や取得障害を調査するための一時的な参考情報として扱う。

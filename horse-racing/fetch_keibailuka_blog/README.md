# keibailukaブログ解析

`keibailuka.blogspot.com` の中央競馬予想ブログ「全レース中の強き不利馬達」を、Chatでの定型依頼から自動取得・解析する独立ツールです。

このツールは `horse-racing/jrdb/` や `horse-racing/eval/` とは別系統です。JRDBデータ基盤、RaceNote、Eval表OCR・検証には依存せず、ブログ由来の予想情報を取得・整形することだけを担当します。

## Source of truth

GitHub `yukki0113/GPT` の `main` ブランチ配下 `horse-racing/fetch_keibailuka_blog/` をPython・README・作業手順・依存関係の正本とします。

- Python: `src/fetch_keibailuka_blog.py`
- 依存: `requirements.txt`
- Chat用Workflow: `.github/workflows/keibailuka_chat.yml`
- GPT運用ルール: `.gpt/CONTEXT.md`, `.gpt/WORKFLOW.md`

日次の解析JSON / TSV、validation、ログ、artifactはGit管理対象外です。

## 通常入力

ユーザーから通常受け取るのは次の2点だけです。

- 対象日 (`YYYY-MM-DD`)
- 開催場の表示順

個別記事URLは通常入力にしません。記事URL探索もモジュール側で行います。

例:

```text
8/23 のブログの解析をお願いします。
開催順：新潟→中京→札幌
```

## CLI

```bash
python horse-racing/fetch_keibailuka_blog/src/fetch_keibailuka_blog.py \
  --date 2026-08-23 \
  --venues 新潟 中京 札幌 \
  --output-dir ./output_keibailuka_20260823
```

オプション:

- `--interval`: HTTPアクセス間隔。既定 `0.8` 秒
- `--timeout`: 1リクエストのタイムアウト。既定 `20` 秒

## 取得経路

検索エンジンのインデックスには依存しません。

最優先は **Blogger公開JSON feedに含まれる記事本文HTML** です。個別記事URLがHTTP 429になる場合でも公開feedが取得できることがあるため、feed本文だけで1R〜12Rを解析できる場合は個別記事ページへアクセスしません。

探索・取得は概ね次の順序です。

1. 対象日前後を指定したBlogger公開JSON feed
2. 直近100件のBlogger公開JSON feed
3. ブログトップ
4. 対象月アーカイブ
5. 前月アーカイブ
6. Bloggerブログ内検索
7. feed本文が無い場合のみ個別記事通常表示
8. 個別記事 `?m=1` モバイル表示

記事タイトル中の `YYYY/M/D`、開催場、`全レース中の強き不利馬達` を照合して対象記事を確定します。

## 解析ルール

記事本文から各場 `1R`〜`12R` を抽出し、次を適用します。

- `該当無し` → 出力しない
- `勝負レース` または `note.com/keibailuka/n/` への有料導入 → 出力しない
- `🤡` → 馬名を `🤡` として出力する
- 🤡欄の「noteにスキボタンを押すと馬名表示」文言 → コメントから除去する
- 通常馬 → 見出し中の馬名と直下コメントを出力する
- 開催場は依頼で渡された順、各場内は1R〜12R順を維持する

ブログ本文の意味を変える要約はPythonでは行いません。空白・CTA等だけを正規化し、長いコメントの軽い要約はChat側で行います。

## 検証

各場について次を必須条件とします。

- 対象記事が一意に見つかること
- 1R〜12Rが順番どおり12個存在すること
- 各Rが `included` または `excluded` に分類できること
- 馬名を推測しないこと。見出しから安全に取れない場合は `parse_error` とすること
- `included + excluded = 12`

条件を満たさない場合はvalidationをfailureとして終了コード2を返し、部分取得を成功扱いしません。

## Chat / GitHub Actions

Chatからの定型解析は `.github/workflows/keibailuka_chat.yml` のIssue経路を標準とします。

- Issue title: `[KEIBAILUKA_REQUEST] <request_id>`
- Issue body: `date` と `venues` を持つJSON

ActionsはGit正本のPythonを実行し、結果JSON / TSV / validationをartifact化します。完了後、同じIssueへ `KEIBAILUKA_RESULT` コメントを返し、自動クローズします。

成功条件は次の3点です。

- `fetch_exit_code = 0`
- `validation_exit_code = 0`
- `validation.validation_status = success`

結果コメントにはsource URL、採用entries、Plain text TSV、run/artifact情報を含めます。通常のChat回答はこの結果コメントから組み立てます。

## 実動確認

2026-08-26時点で、URLをユーザー入力せず次の実データで取得・解析・validation成功を確認済みです。

- 2026-08-22 新潟→中京→札幌
- 2026-08-23 新潟→中京→札幌

両日とも個別記事HTMLでは429が起こり得る条件でしたが、Blogger公開feed本文から3場分を取得できました。

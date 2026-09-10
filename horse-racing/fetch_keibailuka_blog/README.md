# keibailukaブログ解析

`keibailuka.blogspot.com` の中央競馬予想ブログ「全レース中の強き不利馬達」を、Chatでの定型依頼から自動取得・解析する独立ツールです。

このツールは `horse-racing/jrdb/` や `horse-racing/eval/` とは別系統です。JRDBデータ基盤、RaceNote、Eval表OCR・検証には依存せず、ブログ由来の予想情報を取得・整形することだけを担当します。

## Source of truth

GitHub `yukki0113/GPT` の `main` ブランチ配下 `horse-racing/fetch_keibailuka_blog/` をPython・README・作業手順・依存関係の正本とします。

- Python: `src/fetch_keibailuka_blog.py`
- 依存: `requirements.txt`
- Chat用Workflow: `.github/workflows/keibailuka_chat.yml`
- GPT運用ルール: `.gpt/CONTEXT.md`, `.gpt/WORKFLOW.md`
- GitHub運用上位方針: `/.gpt/GITHUB_OPERATION_POLICY.md`

日次の解析JSON / TSV / CSV、validation、ログ、artifactはGit管理対象外です。

## GitHub operation routing

2026-09-10以降、GitHubにmoduleがあることだけを理由にIssue / Actionsを選びません。上位方針に従い、処理ごとにA/B/C/Dを判定します。

### A. Read / Audit

次はGitHub read / search / fetchで直接確認し、Issueを作りません。

- latest `main`
- source / README / `.gpt` / workflow
- 既存Issue / `KEIBAILUKA_RESULT`
- run status / artifact metadata / commit / SHA
- 既存成果物の監査

### B. Git Change

source / docs / config / workflow等のUTF-8テキスト変更は、原則GitHubへdirect create / update / deleteしてremote commitを作ります。

`[gpt-git-update]` Issueは標準経路ではなく、direct writeが利用できない場合だけ互換フォールバックとして使います。

変更前は `latest main -> path存在 -> current content/blob SHA -> 必要差分` の順で確認します。

### C. Pure Deterministic Execution

すでに取得済みの固定入力に対する次の処理は、可能な限りGPTローカルで実行します。

- `KEIBAILUKA_RESULT` / JSON / TSV / CSVの並び替え・比較
- 5列CSVへの決定的整形
- SHA-256 / row count / schema確認
- 固定成果物同士の差分確認
- 外部HTTPを必要としないfocused test / regression

このため、成功runからコードブロックを整形するだけの処理や、既存entriesから所定の5列CSVを確認・再生成するだけの処理のために、新しいIssue / Actionsを起動しません。

### D. Actions-Native Execution

**日次のブログ探索・取得・解析・validationは、現行Chat環境ではIssue / Actionsを維持します。**

理由は、正本 `src/fetch_keibailuka_blog.py` がBlogger公開feed / blog pageへ直接HTTPアクセスして記事探索から実行する一体型moduleである一方、現行ChatのローカルPython実行環境では外部hostへのDNS / HTTPアクセスが利用できず、正本moduleを同一条件でローカル実行できないためです。

このmoduleではSecretsやimmutable freezeを理由にActionsを使っているわけではありません。将来、Chat側で正本moduleの外部HTTP実行をそのまま再現できる環境になった場合は、あらためてCへの移行可否を判定します。

日次取得のIssue発行前には `/.gpt/GITHUB_OPERATION_POLICY.md` と `/.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflightを適用し、latest main / workflow parser / request JSONを確認してから1回だけ発行します。

既存runのartifactを読むだけの場合はAで直接取得し、artifact取得のためだけに別Issueを作りません。artifactは通常14日保持の一時成果物であり、このプロジェクトではimmutable freeze /正式監査正本とは定義しません。

## 通常入力

ユーザーから通常受け取るのは次の2点だけです。

- 対象日 (`YYYY-MM-DD`)
- 開催場の表示順

個別記事URLは通常入力にしません。記事URL探索もモジュール側で行います。

例:

```text
9/6 のブログの解析をお願いします。
開催順：札幌→阪神→中山
```

## CLI

```bash
python horse-racing/fetch_keibailuka_blog/src/fetch_keibailuka_blog.py \
  --date 2026-09-06 \
  --venues 札幌 阪神 中山 \
  --output-dir ./output_keibailuka_20260906
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
- 最終出力は1R→12RのR順とし、同一R内では依頼で渡された開催場順を維持する

ブログ本文の意味を変える要約はPythonでは行いません。空白・CTA等だけを正規化し、長いコメントの軽い要約はChat側で行います。

## 出力ファイル

成功時は指定された `output-dir` に次を生成します。

- `keibailuka_YYYYMMDD.json`: 解析結果・source情報・全R分類を含む機械可読JSON
- `keibailuka_YYYYMMDD.tsv`: Chatのコードブロック表示用。列は `場所 / R / 馬名 / コメント`
- `keibailuka_YYYYMMDD.csv`: PWA等への受け渡し用。列は `日付 / 会場 / R / 馬名 / コメント`
- `validation_report.json`: 1R〜12R構造・除外・parse errorのvalidation

TSV / CSV / JSONの `entries` は、1R→12Rの順で、同一R内は依頼された開催場順に並びます。`該当無し` と有料導入は含めず、`🤡` はそのまま保持します。

CSVはUTF-8・ヘッダー付きで、日付は `YYYY-MM-DD`、Rは `1R`〜`12R` 形式です。これはPWA新聞の `keibailuka` addonへ渡すsource payloadであり、JRDB / PWA側の最終join keyをこの抽出処理で推測しません。

## 検証

各場について次を必須条件とします。

- 対象記事が一意に見つかること
- 1R〜12Rが順番どおり12個存在すること
- 各Rが `included` または `excluded` に分類できること
- 馬名を推測しないこと。見出しから安全に取れない場合は `parse_error` とすること
- `included + excluded = 12`

条件を満たさない場合はvalidationをfailureとして終了コード2を返し、部分取得を成功扱いしません。

## Chat / GitHub Actions

日次の外部取得だけは `.github/workflows/keibailuka_chat.yml` のActions-Native経路を使います。

- Issue title: `[KEIBAILUKA_REQUEST] <request_id>`
- Issue body: `date` と `venues` を持つraw JSON

ActionsはGit正本のPythonを実行し、結果JSON / TSV / CSV / validationをartifact化します。完了後、同じIssueへ `KEIBAILUKA_RESULT` コメントを返し、自動クローズします。

成功条件は次の3点です。

- `fetch_exit_code = 0`
- `validation_exit_code = 0`
- `validation.validation_status = success`

通常のChat回答はAで `KEIBAILUKA_RESULT` を読み、成功条件確認後にコードブロックを返します。長文コメントの軽い要約はコードブロック表示側だけで行い、PWA用CSVのコメントはmoduleが抽出した原文を維持します。

CSVは同じrunのartifactから直接回収できます。固定entriesからの形式確認・比較等はCで処理し、新しいIssueは作りません。

## 実動確認

2026-08-26時点で、URLをユーザー入力せず次の実データで取得・解析・validation成功を確認済みです。

- 2026-08-22 新潟→中京→札幌
- 2026-08-23 新潟→中京→札幌

2026-09-06についても、札幌→阪神→中山でR優先順とCSV生成を含む回帰成功を確認済みです。

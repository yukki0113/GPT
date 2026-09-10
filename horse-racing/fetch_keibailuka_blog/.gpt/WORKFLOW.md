# keibailuka GPT workflow

1. ルート `/.gpt/GITHUB_OPERATION_POLICY.md` を確認する。
2. GitHub `main` の最新状態を確認する。
3. `horse-racing/fetch_keibailuka_blog/README.md`、`.gpt/CONTEXT.md`、本ファイル、対象Python、必要なworkflowを確認する。
4. このツールはJRDB / Evalとは独立したブログ予想取得ツールとして扱い、資産を他領域へ混在させない。
5. 処理開始時にA/B/C/Dの経路を判定する。

## A. Read / Audit

次の確認はGitHub read / search / fetchで直接行い、Issueを作らない。

- latest main
- source / README / `.gpt` / workflow
- Issue / `KEIBAILUKA_RESULT`
- run status / artifact metadata / commit / SHA
- 既存成果物の比較・監査に必要な参照

既存runのartifactを読むだけの場合も、追加Issueは作らず直接回収する。

## B. Git Change

Python / docs / config / workflow等のUTF-8テキスト変更は、原則GitHubへdirect create / update / deleteしてremote commitを作る。

変更前に必ず以下を確認する。

1. latest main
2. path存在
3. current content / blob SHA
4. 必要な変更内容

`[gpt-git-update]` はdirect writeが利用できない場合だけ互換フォールバックとして使い、標準経路にはしない。

同一目的の複数ファイルは、安全に1commitへまとめられるGit Data API等が利用できる場合は1commitを優先する。

## C. Pure Deterministic Execution

すでに取得済みの固定入力に対する次の処理はGPTローカルで行い、Issue / Actionsを起動しない。

- entries / JSON / TSV / CSVの並び替え・整形
- 5列CSVの形式確認・決定的変換
- SHA-256 / row count / schema確認
- 既存成果物差分
- 外部HTTP不要のfocused test / regression

Chat表示の長文コメント要約は表示用だけとし、PWA用CSVにはmoduleが抽出した元コメントを維持する。

## D. 日次ブログ取得

現行Chat環境では、日次のブログ探索・取得・解析・validationだけをActions-Native Executionとして扱う。

理由: 正本 `src/fetch_keibailuka_blog.py` はBlogger公開feed / blog pageへの外部HTTPアクセスを含む一体型moduleだが、現行ChatのローカルPython環境では外部hostへのDNS / HTTPアクセスを利用できず、正本moduleを同一条件でローカル実行できないため。

Secretsやimmutable freezeが理由ではない。日次artifactは一時成果物であり、正式なimmutable freeze /監査正本とは扱わない。

将来Chat側で正本moduleの外部HTTP実行を同一条件で再現できるようになった場合は、D継続を前提にせず再棚卸しする。

### Issue preflight

Issue作成前に次を確認する。

1. latest main
2. `.github/workflows/keibailuka_chat.yml` のtitle prefix / request parser
3. 必須キー `date`, `venues`
4. dateが `YYYY-MM-DD`
5. venuesが非空・重複なし・許可会場のみ
6. `request_interval_seconds` を指定する場合は0以上
7. request JSONを機械的にserialize
8. 全項目PASS後にIssueを1回だけ発行

上流artifact依存はないため、run_id / artifact_nameのpreflightは日次取得Issueの入力には不要。

### 日次ブログ解析

ユーザーから通常受け取るのは対象日と開催場順だけとする。個別記事URLの探索・提示を求めない。

1. 一意の `request_id` を生成する。
2. タイトル `[KEIBAILUKA_REQUEST] <request_id>` のIssueを作成する。
3. Issue本文はraw JSONとし、`date` と `venues` を渡す。
4. `.github/workflows/keibailuka_chat.yml` がIssue作成をトリガーに `src/fetch_keibailuka_blog.py` を実行する。
5. module側ではBlogger公開feed本文を第一選択とし、ブログトップ、月別アーカイブ、ブログ内検索、個別記事通常表示、`?m=1` をfallbackとして使う。
6. 各開催場の記事に1R〜12Rが順番どおり12個存在することを必須条件とする。構造不一致や馬名を安全に確定できないRがある場合は推測補完せずfailureとする。
7. `該当無し` は除外する。`勝負レース` やnote有料記事への導入も除外する。`🤡` は馬名欄を `🤡` として残し、公開されているコメントだけを採用する。
8. 対象Issueの `KEIBAILUKA_RESULT` コメントをAで読む。
9. `fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とする。
10. 成功時は `entries` またはPlain text TSVを基に、`場所 / R / 馬名 / コメント` を1R→12R順、同一R内は依頼された開催場順でコードブロックとして返す。
11. 同じrunの `keibailuka_YYYYMMDD.csv` をPWA用成果物として返す。列は `日付 / 会場 / R / 馬名 / コメント`。
12. CSVを回収する場合はRESULTの `run_id` と `artifact_name` を完全一致で使い、既存artifactをAで直接取得する。追加Issueは作らない。
13. 長いコメントだけ、意味を変えない範囲でChatコードブロック側が軽く要約する。CSVは元コメントを維持する。
14. ユーザーから記事URLが提示された場合も恒常的な入力仕様には変更せず、取得障害やブログ仕様変更の調査材料としてのみ扱う。

### Retry

失敗時はfailed step / result comment / job logをAで確認する。

- request不備: requestを修正し、新しいrequest_idで再発行
- external transient: 原因確認後に新しいrequest_idで再試行
- domain validation failure: 盲目的にretryせず記事構造を確認
- implementation error: Bでコード修正後、必要な回帰を実施

同じrequestを理由確認なしでblind rerunしない。

## 改修

1. Pythonやworkflowを改修する場合はREADME / `.gpt` の記載も同時に確認する。
2. テキスト変更はBを標準とし、Git更新Issueは作らない。
3. 外部HTTP不要のtestは可能ならCで実行する。
4. 実日付のBlogger取得を含む回帰が必要な場合だけDでIssueを1回発行し、1R〜12R構造、除外判定、🤡保持、R優先順、CSV列・日付を確認する。
5. 日次JSON / TSV / CSV、validation、ログ、artifactはGitへcommitしない。

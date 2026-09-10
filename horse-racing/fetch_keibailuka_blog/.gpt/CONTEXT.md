# keibailuka blog project context

## Status

Active。中央競馬予想ブログ `keibailuka.blogspot.com` の日次予想記事を取得・解析する独立領域です。

## Boundary

この領域は `horse-racing/jrdb/` および `horse-racing/eval/` とは別系統です。

- JRDB / RaceNoteのデータ基盤を使用しない
- Eval表の画像取得・OCR・検証・台帳更新を使用しない
- ブログ由来の予想情報の取得・整形だけを担当する

関連ソースや運用ルールは `horse-racing/fetch_keibailuka_blog/` 配下に置き、JRDB / Eval配下へ混在させません。

## Source of truth

Python、README、作業手順、依存関係、GitHub Actions WorkflowはGitHub `yukki0113/GPT` の `main` を正本とします。

本体は `src/fetch_keibailuka_blog.py` です。通常入力は対象日と開催場順だけとし、ユーザーへ個別記事URLの探索・提示を求めません。

GitHubのアクセス・更新・Actions利用判定はルート `/.gpt/GITHUB_OPERATION_POLICY.md` を上位方針とします。

## Acquisition

Blogger公開JSON feedに含まれる本文HTMLを第一選択とします。個別記事ページはHTTP 429になることがあるためfallbackです。

記事探索は公開feed、ブログトップ、月別アーカイブ、ブログ内検索を利用し、検索エンジンのインデックス反映待ちに依存しません。

現行ChatのローカルPython環境は外部hostへのDNS / HTTPアクセスを利用できず、正本moduleをそのままBloggerへ接続して実行できません。そのため、日次のブログ探索・取得・解析・validationは現時点ではActions-Native Executionとして `.github/workflows/keibailuka_chat.yml` を維持します。

この判断理由はSecretsやimmutable freezeではなく、正本moduleの外部HTTP実行環境です。将来Chat側で同一実行が可能になった場合は再棚卸しします。

## Parsing rules

各開催場の記事は1R〜12Rを機械検証します。

- `該当無し` は除外
- 有料導入は除外
- `🤡` は馬名欄を `🤡` のまま保持
- 公開コメントだけを採用
- 馬名を安全に確定できない場合は推測せずfailure
- 最終順序は1R→12RのR順、同一R内は依頼された開催場順

Pythonはコメントの意味を変える要約を行いません。長文の軽い要約はChat側のコードブロック表示に限る責務です。

## PWA handoff

成功時はJSON / TSVに加えて `keibailuka_YYYYMMDD.csv` を生成します。CSV列は `日付 / 会場 / R / 馬名 / コメント` です。

このCSVはPWA新聞の `keibailuka` addonへ渡すsource payloadです。抽出処理はブログ由来情報だけを担当し、JRDB / PWA側のvenue code・horse no等の最終join keyを馬名から推測しません。

PWA用CSVのコメントはmoduleが抽出した原文を維持します。Chat表示で長文を軽く要約してもCSVへ反映しません。

## GitHub routing

- A Read / Audit: latest main、source、workflow、Issue、`KEIBAILUKA_RESULT`、run、artifact metadata、SHA等を直接読む。Issue不要。
- B Git Change: source / docs / config / workflow等のUTF-8テキスト変更はGitHubへdirect write。`[gpt-git-update]` はfallbackのみ。
- C Pure Deterministic Execution: 取得済みJSON / entries / TSV / CSVの整形、比較、SHA、row count等はGPTローカルで行う。Issue不要。
- D Actions-Native Execution: 日次のBlogger探索・取得・解析・validationのみ、現行Chat環境ではIssue / Actionsを使う。

既存runのartifactを回収する行為自体はAであり、そのための追加Issueを作りません。日次artifactは一時成果物であり、immutable freeze /正式監査正本ではありません。

## Chat execution

日次取得では、latest mainとworkflow request parserをAで確認してから、`[KEIBAILUKA_REQUEST] <request_id>` Issueを1回だけ作成します。本文JSONに `date` と `venues` を渡します。

Actions完了後の `KEIBAILUKA_RESULT` コメントをAで読み、`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` の3条件を満たした結果だけを採用します。

成功後のコードブロック整形や固定成果物の比較・検査はCで行います。CSVは同じrunのartifactから直接回収でき、artifact取得だけを目的とした新規Issueは作りません。

日次JSON / TSV / CSV、validation、ログ、artifactはGit管理対象外です。

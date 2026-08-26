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

## Acquisition

Blogger公開JSON feedに含まれる本文HTMLを第一選択とします。個別記事ページはHTTP 429になることがあるためfallbackです。

記事探索は公開feed、ブログトップ、月別アーカイブ、ブログ内検索を利用し、検索エンジンのインデックス反映待ちに依存しません。

## Parsing rules

各開催場の記事は1R〜12Rを機械検証します。

- `該当無し` は除外
- 有料導入は除外
- `🤡` は馬名欄を `🤡` のまま保持
- 公開コメントだけを採用
- 馬名を安全に確定できない場合は推測せずfailure
- 最終順序は依頼された開催場順、各場1R〜12R順

Pythonはコメントの意味を変える要約を行いません。長文の軽い要約はChat側の責務です。

## Chat execution

標準実行経路は `.github/workflows/keibailuka_chat.yml` です。

Chatが `[KEIBAILUKA_REQUEST] <request_id>` Issueを作成し、本文JSONに `date` と `venues` を渡します。Actions完了後の `KEIBAILUKA_RESULT` コメントを完了通知として利用します。

日次JSON / TSV、validation、ログ、artifactはGit管理対象外です。

# GPT Project Repository

ChatGPT / Work と連携して継続開発するプロジェクトのソース・仕様を管理する正本リポジトリです。

## Active projects

- `horse-racing/jrdb/` — 中央競馬・JRDBデータ基盤 / RaceNote
- `horse-racing/eval/` — 中央競馬・Eval表取得・検証
- `boat-racing/` — 競艇AI予想の取得・運用ツール

## Legacy

- `horse-racing/legacy/` — 旧JRA-VAN / 検証ラボ等の凍結資産

## Storage policy

GitHubはソース・仕様・スキーマ・小規模テスト資産の正本です。認証情報、有料原データ、大容量SQLite、日次成果物、Excel台帳、キャッシュ、ログは格納しません。

作業開始時は対象プロジェクトの `README.md` と `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` を確認してください。

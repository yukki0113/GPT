# JRDB project context

## Status
Active。中央競馬データ基盤をJRA-VANからJRDBへ移行した現行系です。

## Source of truth
- Python / SQL / schema / docs: このGitディレクトリ
- JRDB Raw ZIP / 大容量SQLite等: Git外ストレージ
- 秘密情報: 環境変数またはローカル `jrdb_secret.py`。Gitへ保存しない

## Important
旧JRA-VAN版の検証ラボは `horse-racing/legacy/` の凍結資産であり、現行実装とは分離します。

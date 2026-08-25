# JRDB project context

## Status
Active。中央競馬データ基盤をJRA-VANからJRDBへ移行した現行系です。

## Source of truth
- Python / SQL / schema / docs: このGitディレクトリ
- JRDB Raw ZIP / 大容量SQLite等: Git外ストレージ
- 秘密情報: 環境変数またはローカル `jrdb_secret.py`。Gitへ保存しない

## External data selection
- Analysis Lite / Stats Mart などの大容量SQLiteは再生成・世代更新でファイル名やGoogle Drive File IDが変わり得るため、Gitには個別のDrive URL / File IDを固定しない。
- 利用時はGit上のREADME・schema・対応ドキュメントで要求versionを確認し、外部ストレージ上から対象期間を満たす最新のvalidation PASS済みartifactを選ぶ。
- AnalysisとStats Martを組み合わせる場合は、schema互換性・対象期間・生成元Analysisの対応関係を確認する。
- 過去時点を再現する分析では、対象日以降の結果が混入しないようas-of条件を必ず設ける。現行YTD Martを過去レースへそのまま適用しない。
- 将来、外部artifact探索を自動化する場合は、変動するFile IDのGit固定ではなく、固定名manifestやDrive側の安定した探索規約を優先する。

## Important
旧JRA-VAN版の検証ラボは `horse-racing/legacy/` の凍結資産であり、現行実装とは分離します。

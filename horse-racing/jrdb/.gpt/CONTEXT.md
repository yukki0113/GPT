# JRDB project context

## Status
Active。中央競馬データ基盤をJRA-VANからJRDBへ移行した現行系です。

## Source of truth
- Python / SQL / schema / docs: このGitディレクトリ
- JRDB Raw ZIP / 大容量SQLite等: Git外ストレージ
- 秘密情報: 環境変数またはローカル `jrdb_secret.py`。Gitへ保存しない

## External data selection
- Analysis Lite / Stats Mart / RaceNote Archive などの大容量artifactは再生成・世代更新でファイル名や外部storage上の識別子が変わり得るため、Gitには個別のDrive URL / File IDを固定しない。
- 利用時はGit上のREADME・schema・対応ドキュメントで要求versionを確認し、外部ストレージ上から対象期間を満たす最新のvalidation PASS済みartifactを選ぶ。
- AnalysisとStats Martを組み合わせる場合は、schema互換性・対象期間・生成元Analysisの対応関係を確認する。
- 過去時点を再現する分析では、対象日以降の結果が混入しないようas-of条件を必ず設ける。現行YTD Martを過去レースへそのまま適用しない。
- RaceNote Archiveは固定命名のimmutable GitHub Release assetとrelease metadataを現在の探索indexとして使用する。Router本体へRelease URLを固定せず、`src/resolve_racenote_archive_release.py` が対象月のlatest compatible publishable shardを解決してローカルpathだけをRouterへ渡す。
- その他の外部artifact探索を自動化する場合も、変動するFile IDのGit固定ではなく、固定名manifestや安定した探索規約を優先する。

## RaceNote request entrypoint
- RaceNote取得は `src/racenote_request.py` を統一入口とする。ユーザー/GPTは原則として対象日、任意の開催場、任意のRだけを指定し、過去/当日/未来のsource分岐はrouter内部で行う。
- GPTからの定型実行は `[RACENOTE_REQUEST]` Issue → GitHub Actions → artifact 回収を標準経路とする。詳細は `docs/README_racenote_request.md`。
- GPT-facingな正式RaceNote bundleはschema v1.0。`src/racenote_jrdb.py` のbase v0.2を `src/racenote_history_enrichment.py` でenrichし、`schema/racenote_bundle_schema_v1_0.json` に従う。正式仕様は `docs/README_racenote_v1.md`。
- enrichmentロジックの正本は `src/racenote_history_engine.py`。production `src/racenote_history_enrichment.py` と検証用 `src/racenote_history_enrichment_poc.py` は同じneutral engineを利用し、productionからPoC moduleへの依存は持たない。
- v1.0の履歴はPACI詳細 `recent_runs` 最大5 + Analysis Lite簡略 `older_runs` 最大3。固定8件・キャリア上の完全な直近8戦とはみなさず、`history_coverage.run_layers` を併せて解釈する。
- v1.0の距離レンジは1000-1400 / 1400-1800 / 1800-2400 / 2500+。1400/1800は重複境界、2400は中距離側のみ。exact統計も保持する。
- 統計の `sample_size_band` は none=0 / small=1-19 / moderate=20-49 / sufficient=50+ の説明用母数帯であり、統計的有意性を意味しない。
- 履歴coverageのscopeは `jrdb_jra_history`。海外所属馬・海外遠征について海外戦の完全収録を推測せず、`history_coverage` / `run_layers` を根拠に解釈する。
- 過去日では `as_of_exclusive = target_date` を強制し、対象レース結果および対象日以降の結果を利用しない。

## RaceNote Archive production
- `RaceNote Archive` は過去RaceNoteの大量・反復取得用historical base delivery cache。詳細は `docs/RaceNote_Archive_Design_v0_1.md`、SQLite schemaは `schema/racenote_archive_schema_v1_0.sql`。
- Archiveへ保存するのは **base RaceNote v0.2** のみ。Analysis Lite / Stats Mart enrichment済みfinal v1.0は保存しない。request時にcurrent production enrichmentを適用してfinal v1.0を生成する。
- Archive schema v1.0はRaceNote bundle schema v1.0とは別version軸。1暦月1 SQLite、1race=1 zlib-compressed JSON BLOB、lookup keyは `race_date + venue_code + race_no`。
- 過去requestはpublishable full-month Archiveを優先し、Archive未整備・resolver失敗・validation拒否時は既存safe fallback（2026+ PACI / <=2025 annual Raw reconstruction）を維持する。
- ArchiveはRaw/Coreを置換しない。Raw/Coreはaudit/rebuild source truthのまま、Archiveは高速delivery層だけを担当する。
- 大容量Archive shardはGit外。固定命名 `jrdb_racenote_archive_YYYYMM_v1_0.sqlite`、Release tag `jrdb-racenote-archive-YYYYMM-v1.0`。Gitへ個別のDrive URL / File IDを固定しない。
- publishable条件は `full_month`、authoritative expected identity完全一致、source provenanceあり、SQLite/full bundle validation PASS。partial/test shardはproduction backendで拒否する。
- 2025-08 shardは360R identity完全一致・360/360 full scan PASSで公開済み。2025-08-24新潟11RではArchive経路とannual Raw fallbackのfinal v1.0 semantic SHA-256一致を確認済み。
- 通常 `[RACENOTE_REQUEST]` から対象月Releaseの自動resolution → Archive利用まで実データで確認済み。利用者がArchive path/tagを指定する必要はない。
- 初期coverage拡張候補はAnalysis Lite通常利用期間に合わせ2016年以降。月次追加時も同じpublication contractを維持する。

## Important
旧JRA-VAN版の検証ラボは `horse-racing/legacy/` の凍結資産であり、現行実装とは分離します。
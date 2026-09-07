# JRDB project context

## Status
Active。中央競馬データ基盤をJRA-VANからJRDBへ移行した現行系です。

## Source of truth
- Python / SQL / schema / docs: このGitディレクトリ
- JRDB Raw ZIP / PACI: データ原典 / reproducibility source
- Analysis Lite / Stats Mart / annual Canonical等の共有大容量artifactの所在: Google Drive `JRDB/manifest/jrdb_store_manifest_v1.json`
- ローカルの共有artifact実体: `src/jrdb_store.py` がmaterializeする検証済みcache。手動管理する正本ではない
- RaceNote Archive: immutable GitHub Release asset + release metadata
- 秘密情報: 環境変数またはローカル `jrdb_secret.py`。Gitへ保存しない

## Common JRDB Raw Reader
- `src/jrdb_raw.py` を BAC / KYI / CHA / CYB / SED / SKB / ZED / ZKB / UKC の固定長解釈の正本とする。
- CP932 decode、fixed byte offset、race key / race-horse key / result key、record-length auditはCommon Readerが担当する。
- RaceNote / Eval / Analysis / PWA は consumer adapter で既存schema・label・集計・as-of policyへ投影し、Common Reader対応fieldのbyte offsetを重複実装しない。
- 新しいRaw fieldが必要な場合はconsumerへ直接sliceを追加せず、Common Readerへfieldとcharacterization testを追加してから利用する。
- RaceNote historical fallback / Archive builderのprevious-result参照もKYI/SED/SKB Common Reader keyを使用する。
- P0 production migrationは2026-09-06完了。回帰CIは `.github/workflows/jrdb_common_reader_tests.yml`。

## Shared JRDB Store
- `src/jrdb_store.py` を共有artifactのlogical resolver / verified local cache層とする。
- ConsumerはDrive File IDや恒久ローカルpathではなく `jrdb://...` 論理名を要求する。
- live manifestはGit外の固定名 `JRDB/manifest/jrdb_store_manifest_v1.json`。Gitにはexample/schema/docsだけを置き、変動するDrive File IDを固定しない。
- 現行logical entry:
  - `jrdb://analysis/current` — Analysis Lite v1.2
  - `jrdb://stats/current` — Stats Mart v1.1
  - `jrdb://canonical/2024` — Canonical Annual Shard v0.1 / full 2024 / `FINAL`
- Store Resolverはstorage objectと展開後payloadのsize/SHA-256を検証し、content-addressed cacheへ保存する。ZIPはmanifest指定memberだけを展開する。
- `FINAL` artifactを同一logical nameで黙って差し替えない。変更が必要ならdata version / SHAを明示更新する。
- RaceNote Routerは従来の明示 `--analysis` / `--mart` を優先し、未指定時だけStore manifestから `analysis/current` / `stats/current` をresolveできる。既存GitHub Actionsは明示path互換モードを維持する。
- Store/Canonicalの設計正本は `docs/JRDB_Store_Resolver_v0_1.md` と `docs/JRDB_Canonical_Annual_Shard_v0_1.md`。

## Annual Canonical materialization
- `src/build_jrdb_canonical.py` はCommon Readerのneutral parse結果をannual SQLiteへmaterializeする任意の高速アクセス層。
- Canonical SQLiteはRawを置換せず、固定長解釈の独立正本にもならない。byte offsetは持たず、Common Readerの返却fieldを投影する。
- schema v0.1は `schema/jrdb_canonical_schema_v0_1.sql`。BAC/KYI/CHA/CYB/SED/SKB/UKCを収録し、KYI previous link / trait、SKB特記・馬具は子tableで保持する。
- 2024 shardはDrive `JRDB/10_database/canonical/` へZIP transportで公開済み。live manifestの `jrdb://canonical/2024` は `FINAL`。
- 2024実データ監査: source records 286,540、7 family × 各100件 = 700件field-level mismatch 0、SQLite `integrity_check=ok`。
- 単発RaceNote/Evalまで無条件にCanonicalへ寄せない。Raw/PACI直読が十分速い経路はそのまま維持し、反復・横断アクセスで利益があるconsumerだけ段階的に利用する。

## External data selection
- Analysis Lite / Stats Mart / annual Canonical等、Store登録済み共有artifactはlive manifestを所在正本とし、`src/jrdb_store.py` でlogical nameから解決する。
- Consumerへ個別Drive URL / File IDを固定しない。ローカルpathもcache実体としてのみ扱い、次回実行の恒久設定として記録しない。
- AnalysisとStats Martを組み合わせる場合は、manifest上のschema互換性・対象期間・data versionを確認する。
- 過去時点を再現する分析では、対象日以降の結果が混入しないようas-of条件を必ず設ける。現行YTD Martを過去レースへそのまま適用しない。
- RaceNote ArchiveはStoreとは別に、固定命名のimmutable GitHub Release assetとrelease metadataを探索indexとして使用する。Router本体へRelease URLを固定せず、`src/resolve_racenote_archive_release.py` が対象月のlatest compatible publishable shardを解決してローカルpathだけをRouterへ渡す。
- Store未登録の外部artifact探索を新規自動化する場合も、変動するFile IDのGit固定ではなく、固定名manifestや安定した探索規約を優先する。

## RaceNote request entrypoint
- RaceNote取得は `src/racenote_request.py` を統一入口とする。ユーザー/GPTは原則として対象日、任意の開催場、任意のRだけを指定し、過去/当日/未来のsource分岐はrouter内部で行う。
- GPTからの定型実行は `[RACENOTE_REQUEST]` Issue → GitHub Actions → artifact 回収を標準経路とする。詳細は `docs/README_racenote_request.md`。
- RouterへAnalysis/Martの明示pathが両方渡された場合は従来経路を維持する。未指定がある場合は `--store-manifest` または `JRDB_STORE_MANIFEST` を使いStore Resolverから不足artifactを解決する。
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

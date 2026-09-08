# JRDB project context

## Status
Active。中央競馬データ基盤をJRA-VANからJRDBへ移行した現行系です。

## Source of truth
- Python / SQL / schema / docs: このGitディレクトリ
- JRDB Raw ZIP / PACI: データ原典 / reproducibility source
- Analysis Lite / Stats Mart / annual Canonical等の共有大容量artifact: Google Drive上の検証済み成果物。GPT運用ではGoogle Driveアダプタから都度resolveする
- `src/jrdb_store.py`: local/CLI向けの任意のlogical resolver / verified cache。GPT標準のDrive連携層ではない
- RaceNote Archive: immutable GitHub Release asset + release metadata
- 秘密情報: 環境変数またはローカル `jrdb_secret.py`。Gitへ保存しない

## Common JRDB Raw Reader
- `src/jrdb_raw.py` を BAC / KYI / CHA / CYB / SED / SKB / ZED / ZKB / UKC の固定長解釈の正本とする。
- CP932 decode、fixed byte offset、race key / race-horse key / result key、record-length auditはCommon Readerが担当する。
- RaceNote / Eval / Analysis / PWA は consumer adapter で既存schema・label・集計・as-of policyへ投影し、Common Reader対応fieldのbyte offsetを重複実装しない。
- 新しいRaw fieldが必要な場合はconsumerへ直接sliceを追加せず、Common Readerへfieldとcharacterization testを追加してから利用する。
- RaceNote historical fallback / Archive builderのprevious-result参照もKYI/SED/SKB Common Reader keyを使用する。
- P0 production migrationは2026-09-06完了。回帰CIは `.github/workflows/jrdb_common_reader_tests.yml`。

## External artifact acquisition / Google Drive
- GPTがRaceNoteを生成する際のAnalysis Lite / Stats Mart等のGoogle Drive取得は、ChatGPTのGoogle Driveアダプタを使用する。
- GPTは必要時にDriveを検索・fetchして現行artifactをresolveし、検証できたDrive URLを既存 `[RACENOTE_REQUEST]` 契約へ渡す。
- RaceNote本体へ新しいDrive bridge、Drive API client、恒久File ID依存を追加しない。
- 変動するDrive File IDをGitの運用正本として固定しない。E2E証跡で使用したID/URLは監査記録としてのみ扱う。
- `src/jrdb_store.py` と `JRDB_STORE_MANIFEST` はlocal/CLI互換用途として残すが、GPTの標準Drive取得経路にはしない。
- AnalysisとStats Martを組み合わせる場合はschema互換性・対象期間・data versionを確認する。
- 過去時点を再現する分析では、対象日以降の結果が混入しないようas-of条件を必ず設ける。現行YTD Martを過去レースへそのまま適用しない。
- RaceNote ArchiveはDriveとは別に、固定命名のimmutable GitHub Release assetとrelease metadataを探索indexとして使用する。Router本体へRelease URLを固定せず、`src/resolve_racenote_archive_release.py` が対象月のlatest compatible publishable shardを解決してローカルpathだけをRouterへ渡す。

## Annual Canonical materialization
- `src/build_jrdb_canonical.py` はCommon Readerのneutral parse結果をannual SQLiteへmaterializeする任意の高速アクセス層。
- Canonical SQLiteはRawを置換せず、固定長解釈の独立正本にもならない。byte offsetは持たず、Common Readerの返却fieldを投影する。
- schema v0.1は `schema/jrdb_canonical_schema_v0_1.sql`。BAC/KYI/CHA/CYB/SED/SKB/UKCを収録し、KYI previous link / trait、SKB特記・馬具は子tableで保持する。
- 2024 shardはDriveへZIP transportで公開済み。実データ監査はsource records 286,540、7 family × 各100件 = 700件field-level mismatch 0、SQLite `integrity_check=ok`。
- 単発RaceNote/Evalまで無条件にCanonicalへ寄せない。Raw/PACI直読が十分速い経路はそのまま維持し、反復・横断アクセスで利益があるconsumerだけ段階的に利用する。

## RaceNote request entrypoint
- RaceNote取得は `src/racenote_request.py` を統一入口とする。ユーザー/GPTは原則として対象日、任意の開催場、任意のRだけを指定し、過去/当日/未来のsource分岐はrouter内部で行う。
- GPTからの定型実行は `[RACENOTE_REQUEST]` Issue → GitHub Actions → artifact 回収を標準経路とする。詳細は `docs/README_racenote_request.md`。
- GPT運用ではAnalysis/MartをGoogle Driveアダプタでresolveして既存Issue契約のURLへ渡す。Routerの `--store-manifest` はlocal/CLI互換経路として扱う。
- GPT-facingな正式RaceNote bundleはschema v1.0。`src/racenote_jrdb.py` のbase v0.2を `src/racenote_history_enrichment.py` でenrichし、`schema/racenote_bundle_schema_v1_0.json` に従う。正式仕様は `docs/README_racenote_v1.md`。
- enrichmentロジックの正本は `src/racenote_history_engine.py`。production `src/racenote_history_enrichment.py` と検証用 `src/racenote_history_enrichment_poc.py` は同じneutral engineを利用し、productionからPoC moduleへの依存は持たない。
- v1.0の履歴はPACI詳細 `recent_runs` 最大5 + Analysis Lite簡略 `older_runs` 最大3。固定8件・キャリア上の完全な直近8戦とはみなさず、`history_coverage.run_layers` を併せて解釈する。
- v1.0の距離レンジは1000-1400 / 1400-1800 / 1800-2400 / 2500+。1400/1800は重複境界、2400は中距離側のみ。exact統計も保持する。
- 統計の `sample_size_band` は none=0 / small=1-19 / moderate=20-49 / sufficient=50+ の説明用母数帯であり、統計的有意性を意味しない。
- 履歴coverageのscopeは `jrdb_jra_history`。海外所属馬・海外遠征について海外戦の完全収録を推測せず、`history_coverage` / `run_layers` を根拠に解釈する。
- 過去日では `as_of_exclusive = target_date` を強制し、対象レース結果および対象日以降の結果を利用しない。

## RaceNote Reader View / GPT prediction handoff
- 正式なsource artifactは引き続きRaceNote v1.0 `race_bundle_*.json`。Reader Viewはsource of truthを置換しない。
- `src/racenote_reader_view.py` はv1.0を可逆なReader View v0.1へ変換する。field omission / prediction / scoringは行わず、同一のcontextをhoistしてcompact JSON化する。
- `src/racenote_reader_zip.py` はGPT-side consumer adapter。標準 `[RACENOTE_REQUEST]` artifactをGPTが回収した後に実行し、正本bundle bytesを保持したまま `reader_view_*.json` を追加した別ZIPを生成する。
- Reader Viewは必ず `source_semantic_sha256` とround-trip validationで検証する。検証不能ならReader Viewを予想入力として採用しない。
- 2026-09-08 real-data E2E（2024-12-28中山11R）では、正本264,682 bytes → Reader View 134,621 bytes（49.14%削減）、semantic SHA完全一致、正本raw bytes完全保存を確認。証跡は `docs/RaceNote_Reader_View_E2E_20260908.md`。
- Prediction logic remains outside RaceNote converter/router/Reader View。RaceNoteは観測データとprovenanceを渡し、最終的な比較・印・買い目判断はGPT prediction layerの責務とする。
- ユーザーが「MM/DDの○○N Rを予想して」のように1R予想を依頼した場合、GPTは原則として追加のartifact path入力をユーザーへ求めず、次を一連の定型処理として実施する。
  1. Google Driveアダプタで現行Analysis Lite / Stats Martをresolveする。
  2. 標準 `[RACENOTE_REQUEST]` を実行して対象1Rの正式RaceNote v1.0 artifactを取得する。
  3. GPT-side Reader ZIP adapterでReader Viewを生成・round-trip検証する。
  4. `reader_view_*.json` を第一読込対象にし、必要な詳細確認時のみ対応する `race_bundle_*.json` を参照する。
  5. RaceNote内のas-of-safeな事前情報だけを根拠に予想を組み立てる。過去レースでも対象結果を先に参照しない。
- 予想結果の標準表現・印・買い目・confidence policyはRaceNoteデータ契約とは別versionで定義する。未定義の間はRaceNoteへ暗黙のスコアリング規則を追加しない。

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

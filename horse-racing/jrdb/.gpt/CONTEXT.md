
- Forecast reason provenance uses `RaceNote-Decision-Trace-0.1`.
- Decision Trace binds primary / secondary / concern prose to real Trend / RR /
  Ability / Race Structure / Scenario / Edge evidence.
- Scenario risks are derived and cannot be omitted.
- short-comment evidence must be a subset of Decision Trace.
- canonical doc: `docs/racenote/DECISION_TRACE_v0_1.md`.
# JRDB project context

Last reviewed: 2026-09-23

## Current storage precedence — 2026-09-23

When older dated sections conflict with this block, this block wins for current storage/source routing.

- New JRDB Drive root: `GPT/horse-racing`.
- Raw/reproducibility: `GPT/horse-racing/00_raw`.
- Historical normalized canonical: `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`.
- New derived marts: `GPT/horse-racing/20_mart`.
- Old top-level Drive `GPT/JRDB` is legacy operational compatibility and must not be deleted yet.
- `local-horse-racing` is NAR/local-racing scope, not JRDB Warehouse.
- Cross-layer placement audit: `docs/JRDB_Source_of_Truth_and_Storage_Map_20260923.md`.

## Status
Active。中央競馬データ基盤をJRA-VANからJRDBへ移行した現行系です。

この文書はsubsystemをまたいで保持したい **永続context** を担当します。会話量上限やスレッド移動時の短い再開情報は `.gpt/HANDOFF.md`、実行経路は `.gpt/WORKFLOW.md` を優先して併読します。

## Thread restart rule
- 新スレッドでは `README.md` → `.gpt/HANDOFF.md` → `.gpt/CONTEXT.md` → `.gpt/WORKFLOW.md` → latest main → 対象current docs/contract/source の順で確認する。
- RaceNote開発では `docs/racenote/README.md` と `docs/racenote/FORECAST_GEN0_PLAN.md` もcurrent guideとして読む。legacy確認時のみ `docs/racenote/legacy/README.md` を追加確認する。
- この文書に日付付き実績が残っていても、operational defaultはlatest source + current guide/contractで再確認する。
- 古いhandoff / Issue / audit / fixed SHAを単独でcurrent truthとみなさない。

## Source of truth
- Python / SQL / schema / docs: このGitディレクトリのlatest `main`
- JRDB Raw ZIP / PACI: データ原典 / reproducibility source
- Analysis canonical / annual Warehouse / research DB等の共有大容量artifact: Google Drive上の検証済み成果物。Stats MartはRaceNote current pathから除外されたlegacy-only資産として必要時のみ明示的に扱う
- `src/jrdb_store.py`: local/CLI向けの任意のlogical resolver / verified cache。GPT標準のDrive連携層ではない
- RaceNote Archive: immutable GitHub Release asset + release metadata
- 秘密情報: 環境変数 / GitHub Secrets / ローカル `jrdb_secret.py`。Gitへ保存しない

## Stable identity / join rules
- `race_key` は場2 + 年2 + 回1 + 日1 + R2のraw文字列。日部分はhexを含むためdecimalへ勝手に正規化しない。
- `race_horse_key = race_key + horse_no`。
- `result_key = blood_registration_no + YYYYMMDD`。
- optional source joinは原則LEFT / fail-closed。欠損を推測で補完しない。
- JRDBコード値のreader-facing表示はマスタ定義を参照し、内部codeを説明なしで通常表示へ露出しない。

## Common JRDB Raw Reader
- `src/jrdb_raw.py` を BAC / KYI / CHA / CYB / SED / SKB / ZED / ZKB / UKC の固定長解釈の正本とする。
- CP932 decode、fixed byte offset、race key / race-horse key / result key、record-length auditはCommon Readerが担当する。
- RaceNote / Eval / Analysis / PWA / Edge は consumer adapter で既存schema・label・集計・as-of policyへ投影し、Common Reader対応fieldのbyte offsetを重複実装しない。
- 新しいRaw fieldが必要な場合はconsumerへ直接sliceを追加せず、Common Readerへfieldとcharacterization testを追加してから利用する。
- RaceNote historical fallback / Archive builderのprevious-result参照もKYI/SED/SKB Common Reader keyを使用する。
- P0 production migrationは2026-09-06完了。回帰CIは `.github/workflows/jrdb_common_reader_tests.yml`。

## External artifact acquisition / Google Drive
- GPTがRaceNoteを生成する際のAnalysis canonicalのGoogle Drive取得は、ChatGPTのGoogle Driveアダプタを使用する。Stats MartはRaceNoteのactive pathではresolveしない。
- GPTは必要時にDriveを検索・fetchして現行artifactをresolveし、検証できたDrive URLを既存 `[RACENOTE_REQUEST]` 契約へ渡す。
- RaceNote本体へ新しいDrive bridge、Drive API client、恒久File ID依存を追加しない。
- 変動するDrive File IDをGitの運用正本として固定しない。E2E証跡で使用したID/URLは監査記録としてのみ扱う。
- `src/jrdb_store.py` と `JRDB_STORE_MANIFEST` はlocal/CLI互換用途として残すが、GPTの標準Drive取得経路にはしない。
- 過去時点を再現する分析では、対象日以降の結果が混入しないようas-of条件を必ず設ける。現行YTD Martを過去レースへそのまま適用しない。
- RaceNote ArchiveはDriveとは別に、固定命名のimmutable GitHub Release assetとrelease metadataを探索indexとして使用する。Router本体へRelease URLを固定せず、`src/resolve_racenote_archive_release.py` が対象月のlatest compatible publishable shardを解決してローカルpathだけをRouterへ渡す。

## Annual Canonical materialization
- `src/build_jrdb_canonical.py` はCommon Readerのneutral parse結果をannual SQLiteへmaterializeする任意の高速アクセス層。
- Canonical SQLiteはRawを置換せず、固定長解釈の独立正本にもならない。byte offsetは持たず、Common Readerの返却fieldを投影する。
- schema v0.1は `schema/jrdb_canonical_schema_v0_1.sql`。BAC/KYI/CHA/CYB/SED/SKB/UKCを収録し、KYI previous link / trait、SKB特記・馬具は子tableで保持する。
- 2024 shardはDriveへZIP transportで公開済み。実データ監査はsource records 286,540、7 family × 各100件 = 700件field-level mismatch 0、SQLite `integrity_check=ok`。
- 単発RaceNote/Evalまで無条件にCanonicalへ寄せない。Raw/PACI直読が十分速い経路はそのまま維持し、反復・横断アクセスで利益があるconsumerだけ段階的に利用する。

## Analysis Lite / Stats Mart / post-race generation
- production full rebuild: `src/build_jrdb_analysis_from_raw.py`。
- incremental date replacement: `src/update_jrdb_analysis_incremental.py`。対象日を `DELETE -> INSERT` で原子的に置換し、append重複を避ける。
- Stats Mart: `src/build_jrdb_stats_mart.py` / `src/refresh_jrdb_stats_mart_year.py`。
- PWA condition-summary Fact Lite: `src/build_jrdb_pwa_fact_lite.py`。
- 開催後のRaceNote更新は、検証済みAnalysis Parquet generationを正本として行う。Stats Mart refreshはRaceNote current pathの完了条件ではない。Fact Lite/PWA更新はそれぞれのcurrent contractに従う。
- Analysis canonicalはyear-object ZSTD Parquet v1.3。RaceNoteはcurrent.jsonで解決したgenerationをDuckDB directで読む。Analysis SQLite materializationはRaceNoteのproduction prerequisiteではなく、equivalence/audit/rollback用に限定する。
- JRDB認証取得、formal artifact chain、immutable publication証跡が必要な工程は `.gpt/WORKFLOW.md` のRoute D。既取得入力だけで完結する集計・監査はRoute Cを優先する。
- 旧Stats Mart更新手順は historical/legacy asset であり、RaceNote current operationには使用しない。current workflow/sourceと `docs/racenote/legacy/README.md` を確認する。

## RaceNote request entrypoint
- RaceNote取得は `src/racenote_request.py` を統一入口とする。ユーザー/GPTは原則として対象日、任意の開催場、任意のRだけを指定し、過去/当日/未来のsource分岐はrouter内部で行う。
- JRDB Secretsや正式artifact chainを必要とするGPT定型実行は `[RACENOTE_REQUEST]` Issue → GitHub Actions → artifact回収のActions-native経路を使う。詳細は `docs/README_racenote_request.md`。
- GPT運用ではAnalysis canonicalをGoogle Driveアダプタでresolveして既存Issue契約のURLへ渡す。Routerの `--store-manifest` はlocal/CLI互換経路として扱う。Stats Martはrequest inputではない。
- GPT-facingな正式RaceNote bundleはschema v1.0。`src/racenote_jrdb.py` のbase v0.2を `src/racenote_history_enrichment.py` でenrichし、`schema/racenote_bundle_schema_v1_0.json` に従う。正式仕様は `docs/README_racenote_v1.md`。
- enrichmentロジックの正本は `src/racenote_history_engine.py`。production `src/racenote_history_enrichment.py` と検証用 `src/racenote_history_enrichment_poc.py` は同じneutral engineを利用し、productionからPoC moduleへの依存は持たない。
- v1.0の履歴はPACI詳細 `recent_runs` 最大5 + Analysis Lite簡略 `older_runs` 最大3。固定8件・キャリア上の完全な直近8戦とはみなさず、`history_coverage.run_layers` を併せて解釈する。
- v1.0の距離レンジは1000-1400 / 1400-1800 / 1800-2400 / 2500+。1400/1800は重複境界、2400は中距離側のみ。exact統計も保持する。
- 統計の `sample_size_band` は none=0 / small=1-19 / moderate=20-49 / sufficient=50+ の説明用母数帯であり、統計的有意性を意味しない。
- 履歴coverageのscopeは `jrdb_jra_history`。海外所属馬・海外遠征について海外戦の完全収録を推測せず、`history_coverage` / `run_layers` を根拠に解釈する。
- 過去日では `as_of_exclusive = target_date` を強制し、対象レース結果および対象日以降の結果を利用しない。

## RaceNote Reader View / GPT handoff
- 正式なsource artifactは引き続きRaceNote v1.0 `race_bundle_*.json`。Reader Viewはsource of truthを置換しない。
- `src/racenote_reader_view.py` はv1.0を可逆なReader View v0.1へ変換する。field omission / prediction / scoringは行わず、同一のcontextをhoistしてcompact JSON化する。
- `src/racenote_reader_zip.py` はGPT-side consumer adapter。標準 `[RACENOTE_REQUEST]` artifactをGPTが回収した後に実行し、正本bundle bytesを保持したまま `reader_view_*.json` を追加した別ZIPを生成する。
- Reader Viewは必ず `source_semantic_sha256` とround-trip validationで検証する。検証不能ならReader Viewを予想入力として採用しない。
- 2026-09-08 real-data E2E（2024-12-28中山11R）では、正本264,682 bytes → Reader View 134,621 bytes（49.14%削減）、semantic SHA完全一致、正本raw bytes完全保存を確認。証跡は `docs/RaceNote_Reader_View_E2E_20260908.md`。
- Prediction logic remains outside RaceNote converter/router/Reader View。RaceNoteは観測データとprovenanceを渡し、最終的な比較・印・買い目判断はprediction layerの責務とする。
- 1R予想では、Google Driveから現行Analysis canonicalをresolveし、正式RaceNote v1.0を取得、Reader Viewをround-trip検証し、as-of-safeな事前情報を第一入力として読む。必要な詳細確認時だけ正本bundleへ戻る。

## RaceNote Forecast Gen0 — current prediction research

- 2026-09-25: next-generation contract finalized as **RaceNote-Forecast-Gen0.3**; planned first activation is **Gen0-G001**.
- Gen0.2 was implemented but never activated and is retained as a pre-redesign reference.
- Gen0.3 reading policy: `DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY

Prediction reading layer (2026-09-25):

- `PredictionInterpretation-v0.1` is embedded per horse in General Evidence.
- `RaceNote-All-Runner-Synthesis-0.1` is the canonical full-field draft layer.
- It authors a complete non-scoring draft order after reading every runner.
- Ability cannot be the primary ordering basis.
- low-confidence / mixed / small-sample / RR-contradiction adjacent boundaries become HIGH Pairwise priorities.
- canonical Pairwise request and validation bind to the Synthesis semantic hash and draft order.
- canonical doc: `docs/racenote/ALL_RUNNER_SYNTHESIS_v0_1.md`.
- It organizes trend direction + sample size + redundancy, Race Structure,
  RaceReview hidden/fragile/repeatability/target overlap, and Ability Anchor.
- It does not score or rank.
- Pairwise reads Interpretation first, then verifies raw Evidence lanes.
- canonical doc: `docs/racenote/PREDICTION_INTERPRETATION_v0_1.md`.`.
- pre-Freeze chain: General Evidence -> All-Runner Synthesis -> Pairwise -> Scenario -> Base Forecast -> EdgeDB Performance-only -> Final Forecast -> Freeze.
- current JRDB consensus / current market / Edge Value / RL-Value / Bet Plan are post-Freeze only; Training Edge is excluded from Forecast.
- canonical contract: `docs/racenote/FORECAST_GEN0_3_PREDICTION_CONTRACT_v0_3.md`

RaceReviewDB consumer default (2026-09-25):

- operational source: stable Drive `RaceReviewDB_CURRENT.zip`
- stable file ID: `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`
- resolver: `src/racenote_racereview_current.py`
- normal adapter CLI uses `--racereview-current-cache`
- `--racereview-root` is retained for audit/replay only
- join: JRDB blood registration number; no name fallback
- as-of: `race_date < target_date`
- consumer contract: `docs/racenote/RACEREVIEW_CURRENT_CONSUMER_v0_1.md`
.
- current guide: `docs/racenote/README.md`。
- current research plan: `docs/racenote/FORECAST_GEN0_PLAN.md`。
- origin reference: `docs/RaceNote_Prediction_Handoff_v0_1.md`。
- RaceNote authoritative bundle / Reader Viewはfacts / evidence / provenanceを担当し、prediction policyを内部へ埋め込まない。
- Gen0ではGPTがレース条件、基礎能力、今回条件適性、展開、調教・状態、近走、長期履歴、補助統計、coverage / conflicting evidence / uncertaintyを横比較して予想する。
- fixed weightや単一score/gateを先にcurrent defaultへ置かない。model/ruleを試す場合はGen0自然言語比較と分離し、独立version・blind / TRUE_FORWARDで評価する。
- one-race lifecycleは `pre-race source resolve -> validation -> GPT evidence reading -> comparison -> prediction draft -> pre-result self-audit -> immutable freeze -> result acquisition -> post-race evaluation` の順。結果取得をfreezeより前へ置かない。
- 改善は1Rの勝敗へ即追従せず、原則約50Rを初期改善単位としてreading error / overvaluation / undervaluation / uncertainty / input不足をまとめて監査する。
- EdgeDBをGen0で使う場合もPerformance / Value、CONFIRMED / SUGGESTIVE、overlapを区別し、単一Edgeだけで結論を固定しない。
- Eval / keibailuka等の外部sourceをRaceNote-only Gen0へ暗黙に混ぜない。併用時はsource別に記録して比較可能性を維持する。

## RaceNote legacy deterministic prediction boundary
- v0.2 control baseline / v1.1-P gated prediction / `src/racenote_edge_prediction_policy.py` / `src/run_racenote_v11p_true_forward_day.py` と関連freezeはhistorical reproducibility / benchmark用legacy prediction logic。
- Gen0へ次を隠れた決定規則として持ち込まない: top5固定候補、Good差 `<= 0.04`、stronger Edge polarityによる機械的◎昇格、v1.1-P順位の無条件継承。
- legacy資産は旧予想再現、TRUE_FORWARD監査、比較研究、downstream compatibilityのため保持する。現時点では物理移動しない。
- pre-race guard、as-of validation、source identity、hash、immutable freeze、result-after-freeze、prediction/presentation immutable check等の研究インフラはcurrent Gen0でも再利用してよい。旧prediction ruleと研究インフラを分ける。
- 詳細は `docs/racenote/legacy/README.md`。

## RaceNote Archive production
- `RaceNote Archive` は過去RaceNoteの大量・反復取得用historical base delivery cache。詳細は `docs/RaceNote_Archive_Design_v0_1.md`、SQLite schemaは `schema/racenote_archive_schema_v1_0.sql`。
- Archive status: OPTIONAL CACHE / NOT CANONICAL SOURCE。Archiveへ保存するのは **base RaceNote v0.2** のみ。Analysis canonical enrichment済みfinal v1.0は保存しない。request時にcurrent production enrichmentを適用してfinal v1.0を生成する。
- Archive schema v1.0はRaceNote bundle schema v1.0とは別version軸。1暦月1 SQLite、1race=1 zlib-compressed JSON BLOB、lookup keyは `race_date + venue_code + race_no`。
- 過去requestはpublishable full-month Archiveを優先し、Archive未整備・resolver失敗・validation拒否時は既存safe fallback（2026+ PACI / <=2025 annual Raw reconstruction）を維持する。
- ArchiveはRaw/Coreを置換しない。Raw/Coreはaudit/rebuild source truthのまま、Archiveは高速delivery層だけを担当する。
- 大容量Archive shardはGit外。固定命名 `jrdb_racenote_archive_YYYYMM_v1_0.sqlite`、Release tag `jrdb-racenote-archive-YYYYMM-v1.0`。Gitへ個別のDrive URL / File IDを固定しない。
- publishable条件は `full_month`、authoritative expected identity完全一致、source provenanceあり、SQLite/full bundle validation PASS。partial/test shardはproduction backendで拒否する。
- 通常 `[RACENOTE_REQUEST]` から対象月Releaseの自動resolution → Archive利用まで実データで確認済み。利用者がArchive path/tagを指定する必要はない。

## EdgeDB v0.2 current serving
- current serving contract: `docs/JRDB_Edge_Suggestive_Serving_Contract_v0_2.md`。
- STANDARD activation audit: `docs/JRDB_Edge_v0_2_STANDARD_Activation_Audit_20260911.md`。
- `src/run_jrdb_edge_match_current_v0_2.py` はordinary operational entrypointで、default serving profileは `STANDARD`。
- `src/jrdb_edge_matcher_v0_2.py` のlow-level primitivesは意図的に `CONFIRMED_ONLY` defaultを維持する。embedded callerはSTANDARDを明示opt-inする。
- v0.2 publicationは `edge_registry_active.jsonl`（legacy compatibility）、`edge_registry_suggestive.jsonl`、`edge_serving_catalog_v0_2.jsonl`、publication auditを分離する。ordinary STANDARD consumerはunified catalogを使う。
- SUGGESTIVEはserving evidence classificationでありRegistry promotionではない。通常 `registry_status=REJECTED` のまま。
- CONFIRMEDとSUGGESTIVEはPerformance / Value channelごとに独立して扱う。ACTIVEだから両channel confirmedとは推測しない。
- SUGGESTIVEを「統計的確認済み」と表現しない。
- Performance-positiveとValue-positiveを相互代用しない。Performance-positiveを馬券価値・期待収益の保証として説明しない。
- redundancy group内でもstrength / ROI / lift / q-value等を加算しない。same-directionはevidence level/specificityによるpresentation role、opposite directionはCONFLICTとして保持する。
- EdgeDB servingはevidence delivery。automatic additive point scoreは別calibration contractなしには許可しない。
- current facts / matchingはexact-match・pre-race only。fuzzy matching、推測前走、対象結果、最終オッズ、後日履歴を混入させない。
- Edge current matchingのAnalysis履歴は、通常はvalidated Analysis v1.3 Parquet `current.json` / immutable generationを直接参照する。`src/jrdb_edge_analysis_history.py` がDuckDB lookupを担当する。
- Analysis SQLiteはEdgeの通常正本ではなくrollback / compatibility / equivalence audit用途。storage migrationのためにtransition意味論・matcher・serving thresholdを変えない。
- 2026-09-19 PACIでParquet currentとcompatibility SQLiteを同一STANDARD catalogへ通し、current facts / matchesのbyte identityをIssue #1197 / run 35814265623で確認済み。
- v0.1 matcher / legacy ACTIVE publicationはbackward compatibility資産として保持し、v0.2実装のために意味を書き換えない。

主要module:
- `src/build_jrdb_edge_feature_mart_v0_2.py`
- `src/jrdb_edge_discovery_v0_2.py`
- `src/build_jrdb_edge_registry_v0_2.py`
- `src/apply_jrdb_edge_statistical_guard_v0_2.py`
- `src/build_jrdb_edge_suggestive_publication_v0_2.py`
- `src/build_jrdb_edge_current_facts_v0_2.py`
- `src/jrdb_edge_matcher_v0_2.py`
- `src/run_jrdb_edge_match_current_v0_2.py`

## Existing v1.1-P presentation / reader language
- `src/racenote_prediction_presentation_v0_2.py` はfreeze済みv1.1-P prediction / Edge axis decisionを説明用evidenceへ投影するpresentation layerで、印・順位・Edge判定を再計算しない。
- contractは `docs/RaceNote_Presentation_Comment_Contract_v0_2.md`。既存consumer / historical freezeの表示互換として保持する。
- ordinary reader wordingでは、internal `good` を `基礎総合評価`、axis eligibilityを `逆転許容圏内/圏外`、Performance Edge polarityを `プラス/中立/マイナス` として表現する。
- `Good`, `base_good`, `axis_good_guard`, `performance_edge_polarity`, `family_vote_sum`, raw `POSITIVE/NEUTRAL/NEGATIVE` 等を説明なしで通常コメントへ露出させない。
- 各馬コメントは馬固有の強み・リスク・表示印の説明を中心にし、race-wideの軸逆転mechanicsはレース短評側が担当する。
- `good`は複合基礎評価。JRDBゴール予測などbase scoreへ含まれるcomponentを、Edge比較後の別の独立voteとして二重加算・二重説明しない。
- このpresentation contractはv1.1-PをGen0のcurrent prediction policyへ戻す根拠ではない。current Gen0でも「presentationがfrozen predictionを書き換えない」という境界だけは継承する。

## Newspaper / PWA Edge consumer boundary
- main flow: `PACI + Analysis history -> Edge Current Facts -> Edge Matcher -> edge_matches.jsonl -> Newspaper merge -> PWA / special memo`。
- `src/jrdb_newspaper_merge_edge.py` は `src/jrdb_newspaper_edge_adapter.py` を通してmatcher outputを取り込む。
- Newspaper / PWA側でEdge条件を再計算・再判定しない。
- join identityは `race_key / race_horse_key / horse_no` を中心にfail-closedで扱う。
- `jrdb_newspaper_edge_adapter.py` はdisplay boundary。raw `display_text` / evidence / conditionをaudit用に保持しつつ、reader-facing condition / memoだけを人間向けへ翻訳する。
- 系統code等はJRDB masterで解決できる場合に表示名へ変換する。unknown codeに意味を捏造しない。
- 表示修正はmatching semantics、q threshold、eligibility、raw conditionを変更しない。
- sourceを修正しても既発行day packageは自動で書き変わらない。必要な場合はgeneration/publishを明示的に更新する。
- PWA / Newspaperのdelivery都合でForecast policyを変更しない。安定したfrozen prediction contractをconsumerが表示する。

主要module:
- `src/jrdb_newspaper_build.py`
- `src/jrdb_newspaper_day_build.py`
- `src/jrdb_newspaper_merge_external.py`
- `src/jrdb_newspaper_merge_edge.py`
- `src/jrdb_newspaper_edge_adapter.py`
- `src/jrdb_newspaper_publish_current.py`

## Cross-subsystem prohibitions
- consumer/PWAがupstream evidence logicを重複実装しない。
- historical/current leakageを許さない。
- data transport層をprediction modelへ変質させない。
- internal codeや機械語を通常reader-facing proseへ無説明で出さない。
- legacy v1.1-P decision gateをGen0へ暗黙に持ち込まない。
- contract変更が必要な統計threshold / evidence semantics / publication meaningを、表示修正の名目で変更しない。
- frozen artifactで十分な監査にFull rebuildを習慣的に起動しない。

## Important
旧JRA-VAN版の検証ラボは `horse-racing/legacy/` の凍結資産であり、現行実装とは分離します。


## JRDB historical normalized Warehouse: accepted state (2026-09-21)

The JRDB Warehouse pointer contract is **not** the pre-existing NAR `CURRENT.json`. The only current pointer for this Warehouse is Drive `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`.

It accepts `jrdb_normalized_warehouse_v1_2010_2025_g20260921`: BAC/KYI/CHA/CYB/SED/SKB/ZED/ZKB/HJC/UKC, 2010–2025, 192 Parquet references. Final manifest/audit status is PASS, duplicate object references are zero, and canonical-key/provenance/schema checks are recorded in the final audit. The final generation references existing staging immutable objects; it did not copy, regenerate, or reupload family Parquet.

Canonical finalization code: `src/finalize_jrdb_warehouse_from_staging.py`. Operational contract: `docs/JRDB_Normalized_Warehouse_Operation_v1.md`. Consumer migration remains out of scope until separately authorized.


## Analysis historical Warehouse input boundary — 2026-09-21

A Warehouse Analysis reader and dual-read auditor are available, but there is no production cutover yet. They resolve only the dedicated accepted JRDB Warehouse current generation, project normalized BAC/KYI/SED/CYB/UKC rows into the unchanged Analysis Lite v1.3 logical columns, and require exact Raw-direct equivalence (row count, key, schema, null/blank, all logical values, row hash, representative query, idempotence).

The accepted Warehouse spans 2010–2025. Current 2026 PACI/SED Raw updates remain Raw-direct because that coverage is absent and PACI daily is out of scope. Do not modify any Analysis current pointer until a same-delivery historical audit PASS has been recorded. See `docs/JRDB_Analysis_Warehouse_Input_Contract_v1.md`.


## Analysis input operating split — accepted 2026-09-21

The formal dual-read audit accepted the dedicated JRDB normalized Warehouse as the standard **historical** Analysis input. For 2010–2025 rebuilds/backfills, resolve the JRDB Warehouse current pointer and use `jrdb_analysis_warehouse_adapter.py`; keep historical Raw-direct only as an explicit rollback/audit route. The comparison covered seven deliveries across 2010/2018/2025 (2,866 rows), including count, keys, schema, NULL/blank semantics, all 34 Analysis columns, canonical hashes, representative queries, and repeat-run idempotence.

The 2026 daily route remains PACI/SED Raw-direct. The Warehouse reader is coverage-guarded to 2010–2025 and rejects 2026, preventing an accidental year-boundary cutover. This did not change either the Warehouse current pointer or any existing Analysis current pointer. Normative contract: `docs/JRDB_Analysis_Warehouse_Input_Contract_v1.md`; evidence: `docs/JRDB_Analysis_Warehouse_Dual_Read_Audit_20260921.md`.


## RaceNote Historical Warehouse Phase 1 (2026-09-22)

Contract: RaceNote historical rebuilds (2010–2025) resolve the accepted dedicated JRDB Warehouse current pointer and its immutable Parquet assets, then use the existing RaceNote normalizer unchanged. `racenote_request.py` requires an explicit local current file and verified roots for BAC/KYI/CHA/CYB/ZED/ZKB; 2026 remains the PACI/Raw route. Raw is retained for audit, rollback, and the explicit 2010 previous-result boundary only.

Formal dual-read PASS: 2018-12-28 (24 races / 368 horses / 1,184 previous-result keys) and 2025-12-28 (24 races / 356 horses / 1,160 previous-result keys). Gates: row count, primary keys, schema, NULL/blank semantics, all logical values, Archive semantic hash, repeated-read determinism, idempotence. The 2010 KYI scan found 65,835 references to 2009 result keys; those require recorded Raw fallback because Warehouse coverage begins in 2010.
## RL-T production Warehouse boundary — 2026-09-26

RL-T production historical upstream is now cut over to the accepted JRDB Historical Warehouse generation `jrdb_normalized_warehouse_v1_2010_2025_g20260921`.

Normal production route:
- 2010–2025: accepted Warehouse + canonical record-hash compatibility package
- 2026 daily/replay: existing PACI + settled SED / Raw-direct semantics
- Index Base schema / RunPerf / Official RunPerf / Training Edge v0.2 science remain unchanged
- no silent Historical Raw fallback

The three production workflows are:
- `.github/workflows/jrdb_training_edge_v02_daily_issue.yml`
- `.github/workflows/jrdb_training_edge_v02_replay_issue.yml`
- `.github/workflows/jrdb_training_research_issue.yml`

Static production audit PASS: Issue #1520 / run `36242350903`.
Fixed replay/scorer boundary PASS: Issue #1517 / run `36240031550`.
Training Research Warehouse build PASS: Issue #1518 / run `36240033827`.

A separate current-forward runtime fingerprint drift observed on 2026-09-27 is tracked in Issue #1521. Treat it as an operational/scientific guard investigation, not as permission to revert the Historical source to Raw or to modify the frozen v0.2 fingerprint.


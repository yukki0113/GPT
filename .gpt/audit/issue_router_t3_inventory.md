# Issue Router T3 inventory

- Base: `5f2e5b2e9807bff54bf84e5561e5273c8ffc40f5`
- Workflow files: 200
- `issues: opened`: 121
- 分類: A=7, B=99, C=10, D=5
- `migration_candidate=true` は構造上の候補であり、移行確定ではない。
- YAML parse error: .github/workflows/jrdb_newspaper_current_audit_issue.yml

| Class | Workflow | Prefix | Project | Risk | Reason |
|---|---|---|---|---|---|
| B | `.github/workflows/boatrace_pre_race_issue.yml` | `[BOATRACE_PRE_RACE_REQUEST]` | boat-racing | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/boatrace_results_chat.yml` | `[BOATRACE_RESULTS_REQUEST]` | boat-racing | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| D | `.github/workflows/data_storage_fallback_issue.yml` | `[DATA_STORAGE_FALLBACK]` | repository-common | high | 共通Router・互換/運用入口。個別prefixの機械移行対象外 |
| B | `.github/workflows/edgedb_v05_positive_freeze_issue.yml` | `[EDGEDB_V05_POSITIVE_FREEZE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/eval_jrdb_dataset_issue.yml` | `[EVAL_JRDB_DATASET]` | horse-racing/eval | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/eval_media_chat.yml` | `[EVAL_MEDIA_REQUEST]` | horse-racing/eval | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/eval_ocr_chat.yml` | `[EVAL_OCR_REQUEST]` | horse-racing/eval | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| D | `.github/workflows/gpt_git_binary_read_issue.yml` | `[gpt-git-binary-read]` | repository-common | high | 共通Router・互換/運用入口。個別prefixの機械移行対象外 |
| D | `.github/workflows/gpt_git_update_issue.yml` | `[gpt-git-update]` | repository-common | high | 共通Router・互換/運用入口。個別prefixの機械移行対象外 |
| D | `.github/workflows/issue_router.yml` | — | repository-common | high | 共通Router・互換/運用入口。個別prefixの機械移行対象外 |
| B | `.github/workflows/jra_results_chat.yml` | `[JRA_RESULTS_REQUEST]` | other | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb-race-review-acceptance.yml` | `[JRDB_RACE_REVIEW_ACCEPTANCE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_ability_compare_issue.yml` | `[JRDB_ABILITY_COMPARE]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_ability_holdout_issue.yml` | `[JRDB_ABILITY_HOLDOUT]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_ability_snapshot_audit_issue.yml` | `[JRDB_ABILITY_SNAPSHOT_AUDIT]` | horse-racing/jrdb | medium | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| B | `.github/workflows/jrdb_analysis_parquet_canonical_issue.yml` | `[JRDB_ANALYSIS_PARQUET_CANONICAL]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_analysis_parquet_shadow_issue.yml` | `[JRDB_ANALYSIS_PARQUET_SHADOW]`<br>`[JRDB_ANALYSIS_V14_SHADOW]`<br>`[RACENOTE_TREND_SMOKE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_analysis_win5_migrate_issue.yml` | `[JRDB_ANALYSIS_WIN5_MIGRATE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| A | `.github/workflows/jrdb_annual_raw_fetch_issue.yml` | `[JRDB_ANNUAL_RAW_FETCH_REQUEST]` | horse-racing/jrdb | medium | 単一prefix・JSON本文・既存JRDB module中心。上流run入力なし。RESULT/close仕様を維持して移行可能 |
| B | `.github/workflows/jrdb_bac_duplicate_inspect_issue.yml` | `[JRDB_BAC_DUP_INSPECT]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_cha_duplicate_inspect_issue.yml` | `[JRDB_CHA_DUP_INSPECT]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_daily_403_probe_issue.yml` | `[JRDB_DAILY_403_PROBE]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| A | `.github/workflows/jrdb_daily_history_fetch_issue.yml` | `[JRDB_DAILY_HISTORY_FETCH_REQUEST]` | horse-racing/jrdb | medium | 単一prefix・JSON本文・既存JRDB module中心。上流run入力なし。RESULT/close仕様を維持して移行可能 |
| B | `.github/workflows/jrdb_debut_ability_coverage_issue.yml` | `[JRDB_DEBUT_ABILITY_COVERAGE]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| C | `.github/workflows/jrdb_debut_ability_smoke_issue.yml` | `[JRDB_DEBUT_ABILITY_SMOKE]` | horse-racing/jrdb | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| B | `.github/workflows/jrdb_debut_ability_snapshot_audit_issue.yml` | `[JRDB_DEBUT_ABILITY_SNAPSHOT_AUDIT]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_edge_analysis_parquet_equivalence_issue.yml` | `[JRDB_EDGE_ANALYSIS_PARQUET_EQ]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| C | `.github/workflows/jrdb_edge_forward_selftest_issue.yml` | `[JRDB_EDGE_FORWARD_SELFTEST]` | horse-racing/jrdb | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| B | `.github/workflows/jrdb_edge_forward_settle_issue.yml` | `[JRDB_EDGE_FORWARD_SETTLE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_legacy_audit_issue.yml` | `[JRDB_EDGE_LEGACY_AUDIT]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_parquet_completion_audit_issue.yml` | `[JRDB_EDGE_PARQUET_COMPLETION_AUDIT]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_registry_build_issue.yml` | `[JRDB_EDGE_REGISTRY_BUILD]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_registry_build_v2_issue.yml` | `[JRDB_EDGE_REGISTRY_BUILD_V2]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_registry_parquet_issue.yml` | `[JRDB_EDGE_REGISTRY_PARQUET]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_registry_v02_issue.yml` | `[JRDB_EDGE_REGISTRY_V02]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_serving_publication_issue.yml` | `[JRDB_EDGE_SERVING_PUBLICATION]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v02_operational_audit_issue.yml` | `[JRDB_EDGE_V02_OPERATIONAL_AUDIT]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v03_b2b_gate_issue.yml` | `[JRDB_EDGE_V03_B2B_GATE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v03_forward_shadow_freeze_issue.yml` | `[JRDB_EDGE_V03_FORWARD_SHADOW_FREEZE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v03_operational_replay_issue.yml` | `[JRDB_EDGE_V03_OPERATIONAL_REPLAY]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v03_shadow_catalog_issue.yml` | `[JRDB_EDGE_V03_SHADOW_CATALOG]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v04_artifact_cleanup_issue.yml` | `[JRDB_EDGE_V04_ARTIFACT_CLEANUP]` | horse-racing/jrdb | high | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| B | `.github/workflows/jrdb_edge_v04_c1_pool_audit_issue.yml` | `[JRDB_EDGE_V04_C1_POOL_AUDIT]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v04_stage_a_issue.yml` | `[JRDB_EDGE_V04_STAGE_A]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v04_stage_b_issue.yml` | `[JRDB_EDGE_V04_STAGE_B]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v04_stage_c1_sharded_issue.yml` | `[JRDB_EDGE_V04_STAGE_C1_SHARDED]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v04_stage_c2a_issue.yml` | `[JRDB_EDGE_V04_STAGE_C2A]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_edge_v04_stage_c_issue.yml` | `[JRDB_EDGE_V04_STAGE_C]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_fact_lite_dual_shadow_issue.yml` | `[JRDB_FACT_LITE_DUAL_SHADOW]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_historical_warehouse_family.yml` | `[JRDB_WAREHOUSE_FAMILY]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| A | `.github/workflows/jrdb_index_base_audit_issue.yml` | `[JRDB_INDEX_BASE_AUDIT]` | horse-racing/jrdb | medium | 単一prefix・JSON本文・既存JRDB module中心。上流run入力なし。RESULT/close仕様を維持して移行可能 |
| B | `.github/workflows/jrdb_legacy_daily_annualize_issue.yml` | `[JRDB_LEGACY_DAILY_ANNUALIZE_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| A | `.github/workflows/jrdb_legacy_family_year_issue.yml` | `[JRDB_LEGACY_FAMILY_YEAR_REQUEST]` | horse-racing/jrdb | medium | 単一prefix・JSON本文・既存JRDB module中心。上流run入力なし。RESULT/close仕様を維持して移行可能 |
| B | `.github/workflows/jrdb_legacy_source_probe_issue.yml` | `[JRDB_LEGACY_SOURCE_PROBE]` | horse-racing/jrdb | medium | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| B | `.github/workflows/jrdb_momotaro_newspaper_publish_issue.yml` | `[MOMOTARO_NEWSPAPER_PUBLISH_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_current_audit_issue.yml` | — | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_day_issue.yml` | `[JRDB_NEWSPAPER_DAY_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_edge_republish_issue.yml` | `[JRDB_NEWSPAPER_EDGE_REPUBLISH]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_edge_v05_republish_issue.yml` | `[JRDB_NEWSPAPER_EDGE_V05_REPUBLISH]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_edgedb_live_parity_issue.yml` | `[JRDB_NEWSPAPER_EDGEDB_LIVE_PARITY]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_external_merge_issue.yml` | `[JRDB_NEWSPAPER_EXTERNAL_MERGE_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_kensho_merge_issue.yml` | `[JRDB_NEWSPAPER_KENSHO_MERGE_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_poc_issue.yml` | `[JRDB_NEWSPAPER_POC_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_skeleton_publish_issue.yml` | `[JRDB_NEWSPAPER_SKELETON_PUBLISH_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_newspaper_v03_rehearsal_publish_issue.yml` | `[JRDB_NEWSPAPER_V03_REHEARSAL_PUBLISH_REQUEST]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_official_existing_ability_audit_issue.yml` | `[JRDB_OFFICIAL_ABILITY_AUDIT]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| C | `.github/workflows/jrdb_official_existing_ability_smoke_issue.yml` | `[JRDB_OFFICIAL_ABILITY_SMOKE]` | horse-racing/jrdb | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| B | `.github/workflows/jrdb_post_race_parquet_dry_run_issue.yml` | `[JRDB_POST_RACE_PARQUET_DRY_RUN]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_post_race_parquet_refresh_issue.yml` | `[JRDB_POST_RACE_PARQUET_REFRESH]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_post_race_refresh_issue.yml` | `[JRDB_POST_RACE_REFRESH]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_prerace_duplicate_inspect_issue.yml` | `[JRDB_PRERACE_DUP_INSPECT]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_pwa_fact_lite_build.yml` | `[JRDB_PWA_FACT_LITE_BUILD]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_pwa_fact_lite_publish.yml` | `[JRDB_PWA_FACT_LITE_PUBLISH]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/jrdb_pwa_publish_data.yml` | `[JRDB_PWA_DATA_PUBLISH]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| C | `.github/workflows/jrdb_retry403_test_issue.yml` | `[JRDB_RETRY403_TEST]` | horse-racing/jrdb | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| A | `.github/workflows/jrdb_runperf_audit_issue.yml` | `[JRDB_RUNPERF_AUDIT]` | horse-racing/jrdb | medium | 単一prefix・JSON本文・既存JRDB module中心。上流run入力なし。RESULT/close仕様を維持して移行可能 |
| B | `.github/workflows/jrdb_runperf_compare_issue.yml` | `[JRDB_RUNPERF_COMPARE]` | horse-racing/jrdb | medium | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| B | `.github/workflows/jrdb_runperf_holdout_issue.yml` | `[JRDB_RUNPERF_HOLDOUT]` | horse-racing/jrdb | medium | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| C | `.github/workflows/jrdb_runperf_smoke_issue.yml` | `[JRDB_RUNPERF_SMOKE]` | horse-racing/jrdb | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| B | `.github/workflows/jrdb_training_stage2b_parquet_issue.yml` | `[JRDB_TRAINING_STAGE2B_PARQUET]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/jrdb_ukc_availability_probe_issue.yml` | `[JRDB_UKC_AVAILABILITY_PROBE]` | horse-racing/jrdb | medium | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| B | `.github/workflows/jrdb_warehouse_research_materialize_issue.yml` | `[JRDB_WAREHOUSE_RESEARCH_MATERIALIZE]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/keibailuka_historical_chat.yml` | `[KEIBAILUKA_HISTORICAL_REQUEST]`<br>`[KEIBAILUKA_ANALYSIS_REQUEST]` | horse-racing/fetch_keibailuka_blog | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| A | `.github/workflows/keibailuka_settlement_issue.yml` | `[KEIBAILUKA_SETTLEMENT_REQUEST]` | horse-racing/fetch_keibailuka_blog | medium | 単一prefixとJSON本文。上流artifact参照なし。close/失敗時の契約は個別維持 |
| A | `.github/workflows/keibailuka_shadow_issue.yml` | `[KEIBAILUKA_SHADOW_REQUEST]` | horse-racing/fetch_keibailuka_blog | medium | 単一prefixとJSON本文。上流artifact参照なし。close/失敗時の契約は個別維持 |
| B | `.github/workflows/keirin_crossyear_structure_audit_issue.yml` | `[KEIRIN_CROSSYEAR_STRUCTURE_AUDIT]` | keirin | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/keirin_historical_10y_backfill_issue.yml` | `[KEIRIN_10Y_BACKFILL]` | keirin | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/keirin_historical_annual_audit_issue.yml` | `[KEIRIN_ANNUAL_AUDIT]` | keirin | medium | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| B | `.github/workflows/keirin_historical_month_poc_issue.yml` | `[KEIRIN_MONTH_POC]` | keirin | medium | 削除操作・ad hoc業務実装・holdout/終端契約・非JSON本文の個別確認が必要 |
| B | `.github/workflows/keirin_historical_probe_issue.yml` | `[KEIRIN_HISTORICAL_PROBE]` | keirin | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/keirin_historical_racelist_probe_issue.yml` | `[KEIRIN_RACELIST_PROBE]` | keirin | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/keirin_historical_structure_probe_issue.yml` | `[KEIRIN_STRUCTURE_PROBE]` | keirin | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| D | `.github/workflows/maintenance_reclassify_stale_issues_20260917.yml` | `[MAINTENANCE_RECLASSIFY_STALE_ISSUES_20260917_RUN]` | repository-common | high | 共通Router・互換/運用入口。個別prefixの機械移行対象外 |
| B | `.github/workflows/nar_backfill_issue.yml` | `[NAR_BACKFILL_REQUEST]` | local-horse-racing | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| C | `.github/workflows/racenote_archive_resolver_test_issue.yml` | `[RACENOTE_ARCHIVE_RESOLVE_TEST]` | horse-racing/jrdb/RaceNote | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| C | `.github/workflows/racenote_archive_test_issue.yml` | `[RACENOTE_ARCHIVE_TEST]` | horse-racing/jrdb/RaceNote | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| B | `.github/workflows/racenote_betting_audit_issue.yml` | `[RACENOTE_BETTING_AUDIT_REQUEST]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| C | `.github/workflows/racenote_btday_0042_0043_temp.yml` | `[RACENOTE_DAILY_BTDAY0042_0043]` | horse-racing/jrdb/RaceNote | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| C | `.github/workflows/racenote_btday_freeze_runner_temp.yml` | `[RACENOTE_FREEZE_RUNNER_SMOKE]` | horse-racing/jrdb/RaceNote | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| B | `.github/workflows/racenote_edge_prediction_freeze_issue.yml` | `[RACENOTE_EDGE_PREDICTION_FREEZE]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_gen0_3_day_author.yml` | `[RACENOTE_GEN03_DAY_AUTHOR]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_gen0_3_realdata_author.yml` | `[RACENOTE_GEN03_AUTHOR]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_gen0_3_realdata_prepare.yml` | `[RACENOTE_GEN03_PREPARE]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_gen0_g001_manifest_issue.yml` | `[RACENOTE_GEN0_G001_MANIFEST]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_gen0_result_acquire_issue.yml` | `[RACENOTE_GEN0_RESULT_ACQUIRE]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_mark_policy_research_v0_1.yml` | `[RACENOTE_MARK_POLICY_V01]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_schedule_issue.yml` | `[RACENOTE_SCHEDULE_REQUEST]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_semantic_author_research_v0_2.yml` | `[RACENOTE_SEMANTIC_AUTHOR_V02]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_semantic_author_research_v0_3.yml` | `[RACENOTE_SEMANTIC_AUTHOR_V03]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_semantic_pairwise_research_v0_2.yml` | `[RACENOTE_SEMANTIC_PAIRWISE_V02]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_v11p_blind_freeze_issue.yml` | `[RACENOTE_V11P_BLIND_FREEZE]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_v11p_repeat_blind_freeze_issue.yml` | `[RACENOTE_V11P_REPEAT_BLIND_FREEZE]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_v11p_repeat_settlement_issue.yml` | `[RACENOTE_V11P_REPEAT_SETTLEMENT]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_v11p_settlement_issue.yml` | `[RACENOTE_V11P_SETTLEMENT]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_v11p_settlement_metrics_issue.yml` | `[RACENOTE_V11P_SETTLEMENT]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/racenote_v11p_true_forward_issue.yml` | `[RACENOTE_TRUE_FORWARD_FREEZE]` | horse-racing/jrdb/RaceNote | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/rlt_historical_warehouse_audit_issue.yml` | `[RL_T_HISTORICAL_WAREHOUSE_AUDIT]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| C | `.github/workflows/rlt_record_hash_compat_direct_smoke_issue.yml` | `[RL_T_RECORD_HASH_COMPAT_DIRECT_SMOKE]` | horse-racing/jrdb | medium | ファイル名が一時検証・smoke・保守用途を示す。現行参照と履歴を個別確認するまで削除しない |
| B | `.github/workflows/rlt_record_hash_compat_export_issue.yml` | `[RL_T_RECORD_HASH_COMPAT_EXPORT]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |
| B | `.github/workflows/rlt_record_hash_compat_split_issue.yml` | `[RL_T_RECORD_HASH_COMPAT_SPLIT]` | horse-racing/jrdb | high | 複数prefix、上流artifact/SHA、またはIssue固有event依存の個別契約 |
| B | `.github/workflows/rlt_warehouse_direct_materialize_issue.yml` | `[RL_T_WAREHOUSE_DIRECT_MATERIALIZE]` | horse-racing/jrdb | medium | JSON本文・RESULT/closeの標準形を満たさない、または契約の個別確認が必要 |

全項目の機械可読監査は `issue_router_t3_inventory.json` を参照。

# 2026 pre-race match freeze: Turn 2 completion

Status: PASS  
Recommendation: `READY_FOR_TURN3_OUTCOME_JOIN`  
Production impact: NONE

## Provenance and coverage

The merged PR #1895 freeze covered 79 PACI dates, 2,502 races and 34,550 runners. Its five missing dates were 2026-05-10 (`PACI260510.zip`), 2026-05-16 (`PACI260516.zip`), 2026-05-31 (`PACI260531.zip`), 2026-08-01 (`PACI260801.zip`), and 2026-10-03 (`PACI261003.zip`). All five are present in the completed input set. The final run downloaded all 84 through the bulk transfer, so exact-ID recovery was available and tested but invoked for 0 files. The inventory has 84 files, final PACI count is 84, and remaining missing count is 0.

PACI and SED both cover 84 dates, 2026-01-04 through 2026-10-04. The completed fact population has 2,658 races and 36,706 runners. All 36,706 SED events joined to PACI; chronology violations: 0. The 2010-2025 accepted Warehouse and strictly earlier 2026 starts were used to recompute transitions and FIRST flags from scratch. The immutable cohort remains 1,620 candidates, SHA-256 `a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9`.

## Going and result-blind boundary

The isolated SED snapshot reads only `race_key` and `track_condition_code`, using the historical exception established by `build_jrdb_edge_feature_mart_v0_2.py`. `jrdb_edge_v02_canonical.track_condition_bucket` maps the code to `GOOD` or `SOFT_OR_WORSE`. Going resolved for 2,658 race keys; UNKNOWN: 0; conflicting codes: 0. All runners in a race receive the same value. The matcher fact schema excludes finish, odds, popularity, payout, result IDM and settlement fields.

## Exact-condition matches

Total match rows: 15,330; unique matched runners: 12,633. Family counts: T1=3,540, T2=5,928, T3=930, T4=1,643, T5=160, T6=3,129. T6 was evaluated and produced 3,129 rows.

## Immutable fingerprints and artifact

| Item | SHA-256 |
|---|---|
| Pre-race facts | `081c69f8b0649b40e7d273fa2e2957179ebefc130bacf93555b6800fd73d8df7` |
| Match freeze | `0b99b90b745aef11655630ed2b1416f71c5664b1a3f133f08fd0d493b68b55f0` |
| PACI input set | `fb1bee2c6ec1183cc15067276122fcd22534c959c0318aee0dbc7d3ce921579f` |
| Isolated going snapshot | `bdb01eaa0a8621f81daf3773fc01de9d4034ae488bde3833d9926ba6c65f9386` |

The previous 79-day partial fact fingerprint `526516f9e5a1f46d96de6484e68a9b04237f6f5d6ac2f80f0c34ad380e5ef5c0` and match fingerprint `fbc6258626e9f407990639b1bcb3cfaad3b7d83666aee418c754d74f79240cf4` are `SUPERSEDED_PARTIAL`.

GitHub Actions run [37612817025](https://github.com/yukki0113/GPT/actions/runs/37612817025) passed all 31 focused tests and produced artifact [11479600272](https://github.com/yukki0113/GPT/actions/runs/37612817025/artifacts/11479600272), digest `sha256:67cb99ac37db7f3be639839fb9fb0a60944b487a9f9a834d6af5f57a3ea9e479`. It contains both row-level Parquet files, manifest, audit, daily and family counts, isolated going snapshot, and PACI input inventory. Daily fact and match fingerprints are in the manifest and artifact.

Turn 3 was not started. No 2026 outcomes, ROI, popularity, odds, or payouts were joined. No candidate pruning or production manifest change was made.

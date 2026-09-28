STATUS: HISTORICAL / LEGACY / SUPERSEDED FOR RACENOTE CURRENT
CURRENT: docs/racenote/README.md

# JRDB 開催後 Analysis / Fact Lite / Pages 更新

## 正本と責務

Analysisの正本はGoogle Drive上のimmutable Parquet generationであり、`current.json`だけが現行generationを指す。SQLiteはPACI + SEDの既存差分ロジックとFact Lite生成に必要な一時materializationに限定する。Analysis SQLite ZIPをDrive正本、Fact Lite入力、PWA配布物へ戻してはならない。

Fact Liteの通常配布・PWA runtimeはParquet / DuckDB-Wasmである。Stats Martは旧思想のSQLite資産として現状維持し、開催後更新の標準工程・完了条件には含めない。

## 2026-09-29 current standard — Analysis v1.4 native Parquet

Analysis current schema is v1.4. Normal post-race Analysis refresh no longer
materializes the full Analysis dataset to SQLite.

Current Drive root:

`/GPT/horse-racing/10_warehouse/analysis/v1/`

Current pointer:

`current.json`

Current generation at this review:

`analysis-v1_4-canonical-20260928-02`

Current operational candidate workflow:

`.github/workflows/jrdb_post_race_parquet_refresh_issue.yml`

Native updater:

`src/build_jrdb_analysis_post_race_parquet_native_v1_4.py`

### Fixed execution split

GitHub Actions and Google Drive transport are intentionally separated.

- Actions may use JRDB Secrets and an **upstream GitHub Actions artifact chain**.
- Actions must not download from or upload to Google Drive directly.
- GPT/native Drive connector resolves and publishes the Drive canonical.
- Drive `current.json` advances only after candidate PASS + Drive round-trip
  validation.

### Fixed refresh order

1. Confirm the Drive Analysis `current.json` generation and the matching most
   recent successful post-race candidate artifact.
2. Start `[JRDB_POST_RACE_PARQUET_REFRESH]` with:
   - `request_id`
   - `dates`
   - `generation_id`
   - `source_run_id`
   - `artifact_name`
   - `expected_source_generation`
3. The workflow downloads only that upstream GitHub Actions artifact, promotes
   its `shadow_current.json` to an execution-local `current.json`, and checks
   that it equals `expected_source_generation`.
4. PACI + SED are acquired with JRDB Secrets.
5. `build_jrdb_analysis_post_race_parquet_native_v1_4.py` replaces only the
   affected year partition(s) and emits a new immutable candidate generation.
6. Required gates include:
   - row count equality
   - canonical key equality
   - schema contract equality
   - row-level equivalence
   - metadata preservation
   - duplicate key rows = 0
   - native Parquet update = true
   - full SQLite materialization = false
7. GPT downloads the successful candidate artifact and publishes only the new
   immutable generation assets to Drive.
8. GPT re-downloads the just-published Drive assets and verifies manifest SHA,
   size, row count and audit independently.
9. Only after that round-trip PASS, update the existing Drive `current.json`
   file in place. Preserve the previous generation for rollback.
10. Rebuild/replace the stable local transport bundle used by GPT-side
    consumers as needed. Do not turn that bundle into an Actions->Drive route.
11. Run consumer smoke from a validated local/Drive-resolved bundle or from the
    formal Actions artifact chain, according to the execution routing policy.
12. Continue to downstream Fact Lite / PWA publication only after Analysis
    current validation succeeds.

### Validated cutover evidence

2026-09-28/29 cutover candidate:

- Issue #1590
- Run `36437363166`
- generation `analysis-v1_4-canonical-20260928-02`
- dates: 2026-09-19, 09-20, 09-21, 09-22, 09-26, 09-27
- total rows after update: 517,622
- period through: 2026-09-27
- duplicate key rows: 0
- as-of violations: 0
- native Parquet update: PASS
- full SQLite materialization: false

RaceNote Trend consumer smoke against the promoted v1.4-02 data also passed
(Issue #1591 / Run `36438532392`).

Artifact-only transport regression also passed after removing direct Drive access
from the workflow (Issue #1592 / Run `36489888125`).

### Legacy route

`.github/workflows/jrdb_post_race_refresh_issue.yml` and the old
`run_jrdb_analysis_post_race_incremental.py` full-SQLite route are retained
for historical compatibility / rollback investigation only. They are not the
normal v1.4 post-race Analysis refresh path.

## 完了報告

- 対象日、前後Analysis generation ID、Analysis row countと対象日row count
- canonical key重複・as-of・対象外行不変の監査
- Drive再取得のmanifest / SHA / size検証
- Fact Lite generation ID、6 relation監査、Pages deployment
- PWAでの新generation検出、通常検索、オフライン検索

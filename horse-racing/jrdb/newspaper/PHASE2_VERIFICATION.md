# Phase 2 implementation evidence — Issue #2329

Base: main `672ef704`. Code-only migration; no merge, production Release update, Pages deploy, or Drive write.

## Boundaries

- PACI-only daily request, Base/history audit, artifact. Old Analysis extras ignored. Independent Analysis/Fact Lite/Stats Mart routes retained.
- Normal external merge rejects the retired Training Edge API/CLI. Legacy source fields are removed at new output serialization; other addons retain their semantics. Race schema accepts both legacy and new data (retired fields no longer required).
- Current publish cleans a copy before serialization and recalculates exact published race SHA/size. Skeleton staging and Pages copies normalize independently. Both personal and Momotaro old Release caches are sanitized during Pages assembly.
- STANDARD and v0.5 republish jobs and production v0.3 Edge rehearsal are disabled with literal false. Their code remains historical evidence for Phase 3. No generic production route invokes the Edge query/matcher. Pages no longer requires Edge preview tests, smoke inputs or Edge completion triggers.
- Active shared-only Kensho and Eval workflows call the common external merge, so old Current addons cannot propagate. Momotaro public allowlist stays unchanged.

## Request/caller inventory

Full-repository hidden-file search for `JRDB_NEWSPAPER_DAY_REQUEST` found the current day workflow, REQUEST_CONTRACT, DAY_REQUEST_V2, `.gpt/legacy_workflows/drive_direct/jrdb_newspaper_day_issue.yml`, and `.gpt/audit/issue_router_t3_inventory.{md,json}`. The latter are historical, not active callers. No second executable request builder/router for this prefix was found. Legacy requests remain accepted without needing migration of immutable request records.

## Tests actually run locally

- `PYTHONPATH=horse-racing/jrdb/src:horse-racing/jrdb/tests python -m unittest discover -s horse-racing/jrdb/tests -p 'test_*momotaro*.py'`: 13 PASS.
- Same PYTHONPATH, unittest modules: `test_newspaper_source_retirement`, `test_jrdb_newspaper_build`, `test_jrdb_newspaper_merge_external`, `test_jrdb_newspaper_publish_current`, `test_jrdb_newspaper_racenote_horse_comment`, `test_newspaper_compact_history_pwa`, `test_jrdb_newspaper_eval_analysis_pwa`: 50 PASS.
- New tests execute the workflow's actual parser with PACI Drive/artifact minimal and legacy requests; reject Training Edge input; generate an audited synthetic PACI-only 24R day with complete history; merge legacy addons into a new revision and validate non-propagation, preserved Eval/RaceNote/RRDB/イルカ/Momotaro, source immutability and SHA/size; check retired jobs and Pages isolation.
- Node confidence and retired newspaper UI contracts PASS. Syntax checks for all newspaper JS, both service workers, Momotaro JS PASS.
- Changed workflow YAML parsed, run scripts passed `bash -n`, embedded Python compiled; Python syntax and `git diff --check` PASS.
- `python horse-racing/jrdb/tests/browser_newspaper_retirement.py`: Chromium, personal + Momotaro at 360/390/430px PASS. Fixture includes retired addons; no retired UI for absent/ERROR/PARTIAL/READY states; personal history 3/5/8, Eval modal and sticky identity retained.

## Current data read-only rehearsal

Downloaded `jrdb-newspaper-current` archive, date 2026-11-01 revision 8. Locally merged into revision 9 (not uploaded), 24 races, PASS; all race SHA/size checked, retired fields absent, source race/manifest hashes unchanged, Momotaro projection completed. Only a local synthetic audit wrapper was supplied to the downloaded staging copy because the Release archive omits operational audit.json. Existing immutable Release bytes were not changed. No Parquet/DuckDB query, acquisition or new Analysis copy was needed.

## Remaining dependencies / incomplete production verification

See `PHASE2_DEPENDENCY_INVENTORY.tsv`: full-repository case-insensitive search, including hidden paths and JSON/JSONL/CSV; each matching file classified as Phase 2 handled, independent retained, or Phase 3. This is a snapshot of references, not authorization to delete them. EdgeDB config, compute/research modules, standalone preview, historical requests/docs/tests and disabled entrypoint bodies remain. Do not remove independent Analysis provenance.

Pages artifact code and local staging were checked; no actual Pages workflow/deployment was run. Phase 1 production screen verification and real Phase 2 delivery completion remain pending review, merge and authorized publication. Mobile checks above are local Chromium checks, not real-device production confirmation.

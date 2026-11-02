# Phase 3 retirement audit — Issue #2334

Base: latest main `d8bb12199b891d37d1101591ba16fece038b9f49`. Scope: source/active-entrypoint cleanup only. No merge/deploy, Release/Drive write/deletion, history rewrite, secret deletion, or immutable revision changes.

## Decision before removal

The Phase 2 list was used as a starting point, not as deletion authorization. Candidate Python modules, their dedicated tests, workflow CLI invocations, Python imports, and independent consumers were examined as a reference graph. A fixed-point closure retained any module referenced by an independent live consumer. A full-repository executable-code scan followed the move to catch references outside the initial project graph.

222 dedicated assets were removed from execution locations and preserved byte-for-byte in `../archive/retired-edge-training/`. This is an archive migration, not destruction of scientific evidence. Original path, new path, SHA-256, classification and reason are recorded individually in `ASSET_MAP.json`. All original paths are absent; all archive digests are tested. Executable source/workflow/preview/test files use a final `.txt` extension. Config/frozen artifacts keep original bytes outside active config paths. Nothing in the archive is copied to Pages.

- 36 workflows: dedicated EdgeDB research/build/evaluation/publication, disabled Newspaper republish/rehearsal, and legacy RL-T entrypoints. `WORKFLOW_TRIGGER_AUDIT.tsv` records each event set. They are outside `.github/workflows`, cannot register as Actions or be dispatched, and have no remaining filename/name references in active workflows (including workflow_run/local uses). Issue Router historical inventories and `.gpt/legacy_workflows` remain inactive evidence, not registered entrypoints.
- 101 dedicated src modules including Training Edge holdout projection, 58 dedicated tests, 24 config assets, and 3 standalone preview assets. Their source bytes remain searchable in the archive. No remaining executable reverse references to archived Python modules were found across the full repository (1091 tracked executable files before the new audit test was staged).
- Replaced operating instructions have full copies under `guidance-before-phase3/`. Historical research notes, frozen daily records, old request JSON, prior dependency audits and scientific documents remain. They are evidence, not current operating instructions.

## Retained independent assets

`SHARED_REVERSE_REFERENCES.json` records two shared modules:

- `jrdb_edge_v02_canonical.py`: used by `jrdb_horse_course_fit.py`; categorical-code utility, not an EdgeDB startup route.
- `jrdb_previous_start_research_ledger.py`: used by RRDB time/pace and quantile audits; unrelated previous-start research remains available.

RaceNote edge performance adapters, prediction policy and frozen experiment workflows remain independent consumers of already-frozen evidence; they do not invoke archived EdgeDB compute modules or put Edge data into Newspaper. They retain explicit owner/request checks. This is a deliberate retention of another project's experiments, not an EdgeDB registry/query/publication startup route.

Shared Warehouse/Index Base record-hash materializers, generic data-storage, independent Training Research Stage1b/Stage2b modules and its Parquet workflow remain. Stage2b's historical comparison to Training Edge is provenance, not a Training Edge scorer. JRDB training_index/追切 and the RaceLap local variable `rl` are not retired RL. Fact Lite/Stats Mart/Analysis source and acquisition routes are unchanged.

The permanent `jrdb_newspaper_retired_sources.py`, legacy input compatibility, current-output serialization guards, source-retirement/UI tests and Momotaro allowlist remain active. Old source keys in schema/provenance/tests are intentional. No attempt was made to erase every textual occurrence of “edge” or “RL”. `PHASE3_RESIDUAL_REFERENCES.tsv` is the refreshed hidden-path/full-file search classification; each remaining reference is independent or historical.

## Precisely defined zero scope

Zero dedicated EdgeDB/Training Edge workflow files in the active Actions directory; zero executable imports/CLI references to archived Python modules; zero active workflow filename/name references to archived workflows; zero normal Newspaper Edge/Training Edge input requirements, output fields or UI restoration in tested legacy-data paths. This does not claim zero words in history, no independent RaceNote experiments, deletion of immutable data, or completion of production delivery.

Restoring an archived file intentionally would require separate review; no generic automatic restore path was introduced. Archived commands and relative links are forensic material and are not expected to execute in place.

## Regression evidence (local)

- Main targeted pytest suite: **92 passed**, 222 archive-byte subtests; Newspaper PACI-only synthetic complete 24R, minimal/legacy actual request parser, source non-propagation, Eval WATCH/MATCH/analysis, RRDB不利分析, RaceNote, イルカ/Momotaro, history 3/5/8, published SHA/size, shared course-fit/previous-start ledger/RaceNote frozen adapters. Four existing NumPy/pandas deprecation warnings, no failures.
- Momotaro unittest discovery: **13 passed**.
- Independent Training Research/Stage2b Parquet pytest: **8 passed**.
- Fact Lite unittest discovery: **15 passed**. Four previously stale assertions expected old shell versions, fixed-path resources and a removed previous-generation cache; test expectations now match the existing config-aware sql.js and single-generation SQLite contract. No Fact Lite implementation or acquisition changes.
- Node confidence and retired newspaper UI contracts PASS; Fact Lite query adapter **2 passed**.
- `browser_newspaper_retirement.py`: personal/Momotaro **360/390/430px PASS**, including retired addon fixtures, no retired UI, personal 3/5/8, Eval analysis modal and sticky identity. These are local Chromium, not production real-device checks.
- Exact `Run PWA focused tests` commands from the changed Pages YAML executed locally PASS. Pages now explicitly sets Python 3.12 and installs pinned jsonschema/PyYAML needed by these tests. No assertion is disabled to bypass missing dependencies. This does not establish the cause or resolution of a previous remote failure.
- Active workflow YAML and local uses validated; modified shell run blocks pass `bash -n`, embedded Python compiles, JS syntax and `git diff --check` PASS.
- `PYTHONPATH=tools/data-storage python -m data_storage check-deps`: healthy DuckDB 1.1.3 / PyArrow 25.0.1, reused without reinstall. Parquet-related tests use synthetic local inputs through the existing domain test entrypoints; execution local, no external dataset acquisition or new storage route.

Commands: `PYTHONPATH=horse-racing/jrdb/src:horse-racing/jrdb/tests python -m pytest` with the targeted newspaper/shared tests; same PYTHONPATH unittest discovery patterns `test_*momotaro*.py` and `*fact_lite*.py`; pytest `test_jrdb_training_research.py test_analyze_jrdb_training_stage2b_parquet.py test_audit_jrdb_training_stage2b_parquet_regression.py`; `python horse-racing/jrdb/tests/browser_newspaper_retirement.py`; Node `test_newspaper_confidence.cjs`, `test_newspaper_edge_v05_production.cjs`, `test_fact_lite_query_adapter.cjs`.

## Production evidence and limits

User-confirmed personal iOS Chrome Edge-column disappearance on 2026-11-02 is accepted evidence for that screen only.

Phase 2 merge: `a9bdf31fe10b9de9b994aeb6a38b91ecbce463b4`, 2026-11-02 12:32 UTC. The post-merge Pages [run 41445534037](https://github.com/yukki0113/GPT/actions/runs/41445534037) **failed in Run PWA focused tests**, before artifact preparation/upload/deploy. Its detailed logs could not be fetched because the runtime denied the signed results-receiver host; jobs/steps and conclusion were read via GitHub API. The latest successful Pages [run 41437299821](https://github.com/yukki0113/GPT/actions/runs/41437299821) is **before** the Phase 2 merge. Later runs at current main were skipped. Do not cite these as Phase 2 deploy success.

Latest successful day-build [run 41201153258](https://github.com/yukki0113/GPT/actions/runs/41201153258) is 2026-10-31, also pre-Phase2. No real PACI-only post-Phase2 successful daily build was found in the queried recent/successful runs.

Current Release asset metadata still reports 2026-10-31 upload. Read-only archive inspection: date 2026-11-01 r8, 24R; retired key occurrences include edge 25, my_index 343, edge_v05 343, edge_matches 318, edge_v05_candidates 24 (including empty/placeholder values). Thus actual Current cleanup is NOT complete. Local r8→r9 and Momotaro projection passed 24R, non-propagation, SHA/size and input-file hash immutability; candidates were not uploaded. A local audit wrapper was supplied because Release omits operational audit.json.

Status: **コード上完了・運用検証待ち**. After review/merge, the authorized operations room must confirm PACI-only daily success, both new Current internals, Pages full deployment success, and personal/Momotaro real-device screens. No publication or data mutation is performed in this PR.

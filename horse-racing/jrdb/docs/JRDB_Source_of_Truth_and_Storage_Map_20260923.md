# JRDB Source of Truth / Storage / Placement Audit — 2026-09-23

## Purpose

This is the cross-layer placement audit after consolidating the normalized JRDB Warehouse under the main Drive `GPT/horse-racing` tree. It distinguishes current authority, legacy operational assets, historical evidence, and technical debt.

## Current authoritative map

### GitHub

```text
horse-racing/jrdb/
  src/       executable shared JRDB / Analysis / RaceNote compatibility code
  schema/    SQL / JSON schema contracts
  tests/     regression and compatibility tests
  docs/      current contracts + dated evidence
  .gpt/      current orchestration context / handoff / workflow
.github/workflows/
             operational CI / Actions entry points
horse-racing/eval/
             Eval-specific workflow / ledger / docs
local-horse-racing/
             NAR/local-racing subsystem; not JRDB Warehouse
```

No Warehouse consumer should be moved into `local-horse-racing`.

### Google Drive

```text
GPT/horse-racing/
  00_raw/
    PACI/
    SED/
    BAC/KYI/CHA/CYB/SKB/ZED/ZKB/UKC/HJC...
  10_warehouse/
    jrdb/
      v1/
        current.json
        generations/
          jrdb_normalized_warehouse_v1_2010_2025_g20260921/
            manifest.json
            audit.json
        jrdb_historical_warehouse_staging/
  20_mart/
    training_research/
    racenote/
  manifest/
```

Warehouse current is the JRDB-only lowercase `current.json`; NAR `CURRENT.json` is separate.

## Legacy Drive tree retained for compatibility

A separate top-level Drive tree still exists:

```text
GPT/JRDB/
  00_raw/
  10_database/
  20_mart/
  manifest/
  90_spec/
  99_temp/
```

It is not the new Warehouse canonical location. It must not be deleted yet because the legacy Store manifest still points to older Analysis/Stats/Canonical artifacts by Drive file ID, and some compatibility paths remain active.

Rule: no new canonical contract should be added against `GPT/JRDB`, but do not bulk-move/delete it until each remaining consumer is explicitly retired or cut over.

## Audit findings

### PASS — Warehouse code placement

The Warehouse finalizer, Analysis/RaceNote/Eval/Index Base Warehouse adapters, builders, and Raw-vs-Warehouse auditors are correctly placed under `horse-racing/jrdb/src`. They consume verified local copies of `current.json` / manifest plus caller-supplied asset roots rather than depending on a fixed Drive parent path.

### PASS — Warehouse documentation authority

Current authority:
- `JRDB_Normalized_Warehouse_Operation_v1.md`
- `JRDB_Analysis_Warehouse_Input_Contract_v1.md`
- `JRDB_Analysis_Warehouse_Dual_Read_Audit_20260921.md`
- `RaceNote_Historical_Warehouse_Operation_v1.md`
- `RaceNote_Historical_Warehouse_Dual_Read_Audit_20260922.md`
- `RL_T_Historical_Warehouse_Cutover_Audit_20260922.md`

Dated audits remain evidence snapshots.

### FIXED — 2026 Raw Drive location references

The frozen Raw inventory already identifies `GPT/horse-racing/00_raw` as its root, but the 2026 Raw reference and several Training Edge workflows still pointed to old PACI/SED folders.

Canonical/current Raw folders:
- PACI: `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`
- SED: `1mm6sU8-skS7K2XYHm2citcorUVyMyL58`

The Daily / Replay / OOT / Drive-preflight workflow constants and the Raw reference were aligned. This is a location-only change; scientific logic is unchanged.

### TECH_DEBT — duplicate Warehouse operation doc

`JRDB_Normalized_Warehouse_v1_Operation.md` is the original build-procedure document. Current operational authority is `JRDB_Normalized_Warehouse_Operation_v1.md`. The older file should be treated as legacy/reference-only.

### TECH_DEBT — project restart/status ambiguity

`.gpt/MIGRATION_STATUS.md`, `.gpt/CONTEXT.md`, and `.gpt/HANDOFF.md` contain valid older migration history and some stale source-location statements. They should carry a short current-precedence block so new threads do not mistake historical paths for current storage truth.

### TECH_DEBT — RaceNote Actions plumbing

`racenote_request.py` is Warehouse-standard for 2010–2025 direct historical rebuilds. The generic `racenote_request_issue.yml` wrapper still has legacy Raw-oriented plumbing and does not automatically materialize all Warehouse inputs when no publishable Archive exists.

This is an operational wiring gap, not a reason to redefine Raw as Historical canonical and not a research blocker.

### TECH_DEBT — RaceNote annual Archive backfill

`backfill_racenote_archive_year.py` and `racenote_archive_year_backfill_issue.yml` remain annual-Raw oriented. Keep them for audit/rollback compatibility; Warehouse-fed publishable Archive backfill can be handled later.

### INTENTIONAL — RL-T / Training Edge Historical Raw route

RL-T Warehouse adapters/auditor exist, but current Training Edge / Training Research historical workflows still build Index Base from annual Raw pending the Index Base equivalence gate. This is intentional not-yet-cut-over state, not a misplaced file. 2026 PACI/SED stays Raw-direct.

### PASS — Eval placement

Eval-specific operational code remains under `horse-racing/eval`; shared JRDB Warehouse compatibility code remains under `horse-racing/jrdb/src`. This split is appropriate.

## Do not do

- Do not move JRDB Warehouse back under `local-horse-racing`.
- Do not use NAR uppercase `CURRENT.json` as JRDB state.
- Do not delete the old top-level `GPT/JRDB` tree yet.
- Do not regenerate/copy accepted Warehouse Parquet merely to make folders look cleaner.
- Do not turn full RaceNote Archive backfill or RL-T formal cutover into a research-start gate.

## Current status

```text
DRIVE_WAREHOUSE_PLACEMENT = PASS
WAREHOUSE_POINTER = PASS
GIT_WAREHOUSE_CODE_PLACEMENT = PASS
CURRENT_WAREHOUSE_DOC_AUTHORITY = PASS
RAW_2026_PATH_ALIGNMENT = PASS_AFTER_FIX
NAR_JRDB_POINTER_SEPARATION = PASS

LEGACY_TOPLEVEL_JRDB_STORE = RETAIN
PROJECT_RESTART_DOC_REFRESH = TECH_DEBT
RACENOTE_ACTIONS_WAREHOUSE_PLUMBING = TECH_DEBT
RACENOTE_FULL_ARCHIVE_BACKFILL = TECH_DEBT
RL_T_HISTORICAL_WORKFLOW_CUTOVER = PENDING_EQUIVALENCE
```

## Operational rule

Before adding a new JRDB Drive path:
1. Raw → `GPT/horse-racing/00_raw`
2. normalized Historical canonical → `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`
3. consumer-derived artifact → `GPT/horse-racing/20_mart/<consumer>`
4. code/schema/current docs → GitHub `horse-racing/jrdb/`
5. dated evidence → `horse-racing/jrdb/docs/`, never newer current truth merely because it exists.

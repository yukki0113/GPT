# JRDB Edge v0.2 WATCH Diagnostic — 2026-09-10

Status: **AUDIT COMPLETE / THRESHOLDS UNCHANGED**

## Scope

This document freezes the WATCH diagnostic for Edge Registry v0.2 without changing any discovery, statistical-guard, Registry, or consumer threshold.

Primary Full source:

- Issue: `#723` — `human-residual-full-2010-2025-f`
- Run: `34363072861`
- Head SHA: `1565ca103cdf290af6c17a457bfa38a5b8180cca`
- Artifact id: `10112738032`
- Artifact digest: `sha256:99da3185c7b3017e67b7a31e2ab198b6c8b03a1586e87ae8228a7c9d89d486af`
- Source years: `2010-2025`

Diagnostic implementation:

- `src/audit_jrdb_edge_watch.py`: temporal WATCH vs statistical downgrade
- `src/audit_jrdb_edge_stat_watch.py`: FDR / directional bootstrap-CI reason decomposition
- ACTIVE q threshold: `0.05`
- PROVISIONAL q threshold: `0.10`
- directional bootstrap CI must exclude zero

Pipeline smoke after CLI-output fix:

- Issue: `#820` — `stat-watch-audit-smoke-2025-c`
- Run: `34425256309`
- Result: `success`
- `regression_tests=0`, `watch_audit=0`, `stat_watch_audit=0`
- Artifact id: `10132435960`
- Artifact digest: `sha256:327572391a1891b411d7cabb32184bb16e7d63a6e8775e09c73dc69d2080d7c2`
- Confirmed artifact outputs: `edge_watch_audit.json/.md`, `edge_stat_watch_audit.json/.md`

## 1. Full Registry status

Full `#723` Registry:

- ACTIVE: `2,572`
- PROVISIONAL: `64`
- DECAYING: `74`
- WATCH: `5,472`

WATCH decomposition:

- `TEMPORAL_WATCH`: `1,663` (`30.39%` of WATCH)
- `STAT_DOWNGRADE_FROM_ACTIVE`: `3,667`
- `STAT_DOWNGRADE_FROM_PROVISIONAL`: `142`
- statistical downgrade total: `3,809` (`69.61%` of WATCH)

## 2. Statistical downgrade reason

Among the `3,809` statistical-downgrade records:

- `ALL_SIGNAL_FDR_AND_CI_FAIL`: `3,736` (`98.08%`)
- `Q_PASS_BUT_CI_FAIL_PRESENT`: `73` (`1.92%`)
- other record-level reasons: `0`

Channel-level counts:

### Performance

- `FDR_AND_CI_FAIL`: `2,891`
- `CI_FAIL_ONLY`: `72`
- `NEUTRAL`: `846`

### Value

- `FDR_AND_CI_FAIL`: `1,829`
- `FDR_FAIL_ONLY`: `3`
- `CI_FAIL_ONLY`: `1`
- `NEUTRAL`: `1,976`

## 3. By temporal pre-statistical status

| Temporal status | Both FDR+CI fail | q pass / CI fail | Total |
|---|---:|---:|---:|
| ACTIVE | 3,610 | 57 | 3,667 |
| PROVISIONAL | 126 | 16 | 142 |
| **Total** | **3,736** | **73** | **3,809** |

## 4. By family

| Family | Both FDR+CI fail | q pass / CI fail | Statistical downgrade |
|---|---:|---:|---:|
| COURSE | 230 | 12 | 242 |
| HUMAN | 41 | 3 | 44 |
| PEDIGREE | 2,660 | 32 | 2,692 |
| RECENT | 22 | 2 | 24 |
| TRANSITION | 783 | 24 | 807 |
| **Total** | **3,736** | **73** | **3,809** |

Broad WATCH decomposition also shows that HUMAN and RECENT WATCH are mainly temporal, while PEDIGREE / COURSE / TRANSITION account for most statistical downgrades.

## 5. High-volume statistical-WATCH templates

Largest statistical-downgrade populations include:

- `SIRE_VENUE_SURFACE_DISTANCE_V2`: `565`
- `SIRE_FRAME_TRANSITION_V1`: `528`
- `SIRE_TURN_DISTANCE_V1`: `521`
- `BROODMARE_SIRE_SURFACE_DISTANCE_V2`: `458`
- `SIRE_SURFACE_DISTANCE_V1`: `452`
- `SIRE_TRACK_CONDITION_V2`: `300`
- `COURSE_EXACT_FRAME_V2`: `214`
- `SIRE_AGE_V2`: `214`
- `SIRE_DISTANCE_CHANGE_V1`: `178`

## 6. Interpretation / decision boundary

The WATCH volume is **not primarily caused by candidates that pass FDR but narrowly fail the bootstrap-CI gate**. `98.08%` of statistical downgrades have all non-neutral signals failing both the FDR and CI conditions.

Therefore this audit does **not** support relaxing the existing q-value or directional-CI thresholds merely to reduce the visible WATCH count. Doing so would predominantly admit statistically weak candidates and would conflict with the v0.2 development rule to diagnose WATCH before recalibration.

The next design question is instead whether `temporal WATCH` and `statistical reject/downgrade` should remain represented identically in the Registry/publication layer. Before changing status semantics, publication or storage, the current Registry schema, publication contract, and consumer behavior must be reviewed.

No threshold, Edge status, candidate template, or current-matching rule is changed by this diagnostic.

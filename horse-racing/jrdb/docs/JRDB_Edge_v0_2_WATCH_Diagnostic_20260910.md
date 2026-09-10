# JRDB Edge v0.2 WATCH Diagnostic — 2026-09-10

Status: **AUDIT COMPLETE / THRESHOLDS UNCHANGED / CI SEMANTICS CORRECTED**

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
- directional bootstrap CI must exclude zero after the q-value prepass is cleared

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

## 2. Statistical downgrade reason — corrected interpretation

The production statistical guard first computes p/q values with bootstrap disabled. It then runs the directional race-date cluster bootstrap only for temporal ACTIVE/PROVISIONAL candidates where at least one non-neutral signal clears the relevant q-value threshold.

Therefore a missing CI on a q-prepass failure means **CI NOT EVALUATED**, not CI failure.

Among the `3,809` statistical-downgrade records:

- q-value prepass failed; bootstrap CI not evaluated: `3,736` (`98.08%`)
- q-value prepass passed; bootstrap evaluated; final CI gate not cleared: `73` (`1.92%`)
- other record-level reasons: `0`

Bootstrap execution counts:

- `bootstrap_samples=0`: `3,736`
- `bootstrap_samples=400`: `73`

Channel-level counts under the corrected semantics:

### Performance

- `FDR_FAIL_CI_NOT_EVALUATED`: `2,891`
- `CI_FAIL_ONLY`: `72`
- `NEUTRAL`: `846`

### Value

- `FDR_FAIL_CI_NOT_EVALUATED`: `1,813`
- `FDR_AND_CI_FAIL` after bootstrap was available through another q-passing channel: `16`
- `FDR_FAIL_ONLY`: `3`
- `CI_FAIL_ONLY`: `1`
- `NEUTRAL`: `1,976`

## 3. By temporal pre-statistical status

| Temporal status | q prepass fail / CI not evaluated | q pass / CI fail | Total |
|---|---:|---:|---:|
| ACTIVE | 3,610 | 57 | 3,667 |
| PROVISIONAL | 126 | 16 | 142 |
| **Total** | **3,736** | **73** | **3,809** |

## 4. By family

| Family | q prepass fail / CI not evaluated | q pass / CI fail | Statistical downgrade |
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

The WATCH volume is **not primarily caused by candidates that clear FDR and then narrowly fail the bootstrap-CI gate**. Only `73 / 3,809` (`1.92%`) reach bootstrap and then fail the final directional-CI gate.

However, it is incorrect to claim that the other `3,736` records fail both FDR and CI. They fail the q-value prepass and therefore the production guard intentionally does not compute their bootstrap CI.

This correction does not change any Registry status or acceptance threshold. It does change the evidence interpretation for future serving-tier research: candidates outside the ACTIVE q threshold cannot be ranked by their existing CI because no such CI has been computed for most of them.

Therefore this audit still does **not** support relaxing q-value or CI thresholds merely to reduce visible WATCH/REJECTED counts. Any lower-confidence serving layer must explicitly decide whether and for which prefiltered candidates an additional bootstrap evaluation should be performed.

No threshold, Edge status, candidate template, or current-matching rule is changed by this diagnostic.

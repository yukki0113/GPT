# JPDB P0 — rider identity and historical as-of evidence contract (2026-11-18)

**Status: REVIEW_REQUIRED / fail closed.** This is a P0 evidence and acceptance specification, not a JPDB production implementation or approval of P1/P4.

## Source authority

- Historical accepted 2023–2025 BAC/KYI/SED warehouse binding: `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`; independent row-join PASS recorded in `JPDB_P0_CURRENT_ROW_JOIN_AUDIT_20261118.md`. Its 142,737 KYI/SED rows and **731 code differences** are a final-archive comparison, not a rider-change event log.
- The same 2023–2025 scan reports 728 mismatch rows with `SED.abnormal_code=0`, 1 with `2`, and 2 with `3`. No mismatch is automatically rejected as an invalid key: zero orphaned KYI/SED keys and horse ID conflicts.
- JRDB current Raw acquisition specification: `JRDB_Daily_Raw_Acquisition_Operation_v0_3.md`. After a meeting, SED/HJC become available as an early snapshot; the following pre-race cycle deliberately fetches revised SED. Canonical SED may be updated in place while Drive revisions retain earlier bytes. A *current* archive does not by itself prove the contents or availability of a prior snapshot.
- `JPDB_P0_SOURCE_AUDIT_20261118.md` documents a **single 2026-11-15** PACI / SED read, where 505/505 joined KYI and SED entries had equal jockey codes and 437/437 prior-result ZED links resolved. This is evidence for that dated sample only, not a guarantee for 2023–2025 historical deliveries.
- KYI `reference_jockey_code` means *reference previous jockey*, never a substitute for a verified actual rider in the previous SED/ZED.
- Physical course epoch begins 2023-01-01 but has PARTIAL attribute status and is not a blanket statement of pre-race historical geometry completeness.

## Distinct rider identities (required not-yet-implemented representation)

| Role | Canonical source | Validity / caution |
|---|---|---|
| `scheduled_jockey_code` | target KYI in a PACI snapshot explicitly proven available before prediction cutoff | May change with later KYI publication; final annual KYI must **not** be mislabeled an as-of snapshot |
| `actual_jockey_code` | matching completed-race SED (or validated ZED historical prior result) | A post-race fact. Never use for that target race's pre-race feature |
| `previous_actual_jockey_code` | previous-result SED/ZED identified by the target KYI prior-result key and blood registration ID | Must verify strict earlier `race_date`, matching horse ID, temporal availability and record revision |
| `rider_change_status` | derived from two *temporally eligible* source records | `SAME`, `DIFFERENT`, `NO_PRIOR_LINK`, `PRIOR_NON_JRA`, `OUTSIDE_WINDOW`, `UNAVAILABLE_ASOF`, `KEY_CONFLICT`, `UNKNOWN`; **not** official race-day substitution |
| `official_race_day_substitution` | official rider-change notification and timestamp (not available in these annual archives) | Remains `UNKNOWN` for all 731 mismatches until explicit documentation |

No person-name join may change the identity. Do not map retired, absent or zero current-start riders to nonexistent records.

## As-of eligibility gate

For target prediction time `T` and every source-version record `v`:

1. Verify `v.source_file_sha256`, `v.source_generation`, `v.record_key`, and source-supplied content.
2. Require **source actually available** by `T` (a defensible observed publication/acquisition time; not just final file modification time or race date).
3. Require the fact's event time precede `T` and the latest *eligible* revision be selected **only among versions whose availability time is <= T**. A later SED correction that changes earlier finishing details is forbidden in earlier backtests.
4. For target KYI/PACI, use the most recent verified pre-race available snapshot, never SED for the target race, and never infer a historical final-rider code from retrospective match.
5. For historical race outcomes, separate `FIRST_SED` and `LATE_FINAL_SED` lineage, record `observed_at`, source ZIP SHA, Drive revision or Actions artifact ID, and source release policy.
6. If the source archive's *historical* version, acquisition time, or revision evidence cannot be established, mark `ASOF_UNVERIFIED` and exclude from a claim of authentic historical prediction replay. Finalized retrospective trend analysis may still be reported separately and labeled **NOT AS-OF REPLAY**.
7. When evaluating prior rides, inspect `prev_result_key_1` and provenance before deciding `NO_PRIOR_LINK`. A non-JRA or out-of-window previous result is not a debut.

**Fail-closed invariant:** `eligible(v,T) = known_source_version(v) AND known_available_at(v) <= T AND event_at(v) < T`, with revision lineage and canonical source SHA checked. If availability is unknown, eligibility is unknown — not automatically true.

## P0 acceptance evidence and explicit unfinished work

- **PASS:** 2023–2025 immutable Warehouse row-level BAC/KYI/SED keys and cohort counts.
- **OBSERVED / NOT OFFICIAL CHANGE CLASSIFICATION:** 731 KYI-vs-SED planned/actual differences; preserve samples and group by SED abnormal code. Need original pre-race KYI snapshot and official notification for official substitutions.
- **OPEN:** Historical 2023–2025 pre-race KYI/PACI archive existence and publication times, SED first-release and late-correction revisions, timestamp semantics and availability watermark; 2026-current series coverage and incremental refresh.
- **OPEN:** P1 denominator freeze: `1/2` nonstart, `3` started but not a normal finish, `5` demotion: code label exists in JRDB master-code transcription but exact field-specific and win/place treatment needs inspection. Keep the observed raw code and version `population_filter_id`.
- **OPEN:** Course mapping time-effective join and attribute qualification: see separate Course audit; no assumption that a 2023+ `physical_version_id` constitutes a complete historical course_version registry.
- **NOT AUTHORIZED:** P1 production schema/Reader, P2 statistics, P3 ability claims, P4 RaceNote connection.

The audit decision is **P0 REVIEW_REQUIRED** until the pending availability evidence and versioned population rules are verified. No original data is modified by this document.

# BRDB B1 — actual-start eligibility replay (2026-11-24 JST)

Status: **PARTIAL / PASS_AGGREGATE_REPLAY_RESEARCH_ONLY**. Supersedes only the unresolved start-classification part of the B1 preflight. No training, prediction, display, merge or production authorization.

## Reproduction and provenance

- Source main observed: d96ad6c01aa9771b11b1f74bec34ec619253dc1b.
- Existing B1 preflight SQL (blob 29b3a6386b0b5cbbfeb0cbfd14bd2cbbde116ea9, SHA-256 c23f19b418914c3741be76b6e7ca3a84f013af28e8731a0daebccea2a09db702) restored from Library; all 50 aggregate metrics independently reproduced on the exact input.
- Analysis v1.4 generation analysis-v1_4-postrace-20261115-01 manifest SHA-256 39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d; 10/10 target annual partitions 2016–2025 verified by size and SHA-256. No 2026 data used in this replay.
- Native Drive wheel registry bundle SHA-256 ceee50c7f3e7b2dc74bc8401320d1b69e96cee8d7809383b876677c74c7caa16. Exact bootstrap blob 482b33ec71fcb4435833fd9ce2722f45dedcf896; isolated Python 3.13.5 / DuckDB 2.0.1 / PyArrow 25.0.1 / NumPy 2.2.4. Common dependency_report success. Canonical data_storage.query blob 449fb7977ffb1f7f20a6e649229de122195395bc, common.py blob 3e40574a26e2905fc57f6b167a55c27d12575732. No parser or storage replacement.
- New SQL: [brdb_b1_debut_eligibility_audit_v0_2.sql](../research/brdb_b1_debut_eligibility_audit_v0_2.sql), commit b4b0b02aea1c435611d29f59055f33229a6b81de, blob ddcd7a4b766efbe49040c9331e9ccbfc58f8382e, SHA-256 279ee9c61e9db06b487e473e60a1021b68153c1373d4b0358c58c8f10b259eb2. Git readback exact. Two executions returned identical ordered aggregate rows.
- Local aggregate receipt SHA-256 3e6bd91556cc1272ccf3cff1a3476f13438f4fe5177e985afdadc51b93f7c3c0. No horse-level data committed.
- Official JRDB code table [code__jrdb](https://docs.google.com/document/d/19R1BkuhFE7yfwHH7WWx2Vqx5vMkiRaTiPIBK3FnWyS0/edit) read via canonical Drive folder. A1 新馬, A2 未出走, A3 未勝利; SED 0 normal, 1/2 non-starters, 3/4/5/6 started abnormal. Matches prior [SED audit](BRDB_P0_2_SED_ABNORMAL_STATUS_REVIEW_20261103.md). Class is from race_condition_code, not race_name (all 39,954 A1 names blank). The historical Analysis has no A2 rows.

## Actual-start and eligibility aggregate

| Metric | A1 | All classes |
|---|---:|---:|
| Entry rows | 39,954 | 481,627 |
| Normal finishers | 39,637 | 477,650 |
| Abnormal starters (3/4/5/6) | 152 | 2,229 |
| Non-starters (1/2) | 165 | 1,748 |
| Code-based actual starters | 39,789 | 479,879 |
| First observed JRA start candidate | 35,836 | 42,348 |
| Left edge 2016 | 3,949 | 4,524 |
| Prior history unresolved | 4 | 7,499 |
| Age/history uncertain | 0 | 118 |
| Known prior JRA start | 0 | 425,390 |
| Unknown start status | 0 | 0 |

Historical races 34,548, horses 54,508. A1 races 2,955, horses 39,837. Zero invalid horse IDs, duplicate race/horse_no keys, same-day multiple horse groups, or mixed non-null class codes within races. Classification row count = source row count. No change to frozen normal-finisher denominator in earlier research.

## Prior-link interpretation

A1: 39,832 rows with no prior keys; 118 exact previous horse/date/race joins to non-starter records; 4 previous dates before 2016. No earlier actual JRA starts observed for A1. In the full prior-history-unresolved class, current-link states: before window 6,147; incomplete keys 543; unresolved in-window 793; linked nonstarter with earlier uncertainty 16. A previous-key presence is not equivalent to a prior actual start. The conservative rule excludes the 2016 left edge and unresolved prior links, treats prior abnormal starters as starts, and retains only age 2/3 first-observed candidates after 2016. Unknown or unverified histories are not promoted.

## Annual first-observed candidates

| Year | A1 | All classes |
|---|---:|---:|
| 2017 | 3,882 | 4,555 |
| 2018 | 3,970 | 4,653 |
| 2019 | 4,137 | 4,820 |
| 2020 | 4,231 | 4,762 |
| 2021 | 3,926 | 4,585 |
| 2022 | 3,927 | 4,621 |
| 2023 | 3,910 | 4,712 |
| 2024 | 3,960 | 4,848 |
| 2025 | 3,893 | 4,792 |
| Total | 35,836 | 42,348 |

All-class candidate composition: A1 35,836; A3 6,478; 05 17; OP 3; missing class 14. No missing sire/BMS/line names or codes among candidates; A1 candidate missing track/distance/venue 0, unique horses 35,836; 35,695 normal finishers and 141 abnormal starters. This is field coverage, NOT canonical parent-ID certification.

## Decision and remaining gate

- Separate race-class A1 and first-observed-JRA-start candidate cohorts. Neither is certified global lifetime first start. Analysis is JRA-window-limited; local/overseas starts and the 2016 left edge cannot be certified from this source. Missing or unresolved history is explicitly retained, never inferred from names.
- Use the existing user-accepted historical UKC/KYI equivalence for analytical research (11/18 decision); do not recreate the historical delivery byte/time blocker. This Analysis Lite snapshot lacks canonical parent IDs and selected UKC observation dates; match the accepted date-scoped pedigree asset against B1 keys and record ID/coverage and temporal provenance before authorizing B2/B3 candidate population. This is a separate concrete join/coverage check, not a demand for original historic delivery timestamps.
- B2/B3: distinguish registration, actual-starter, normal-finisher denominators; predefine handling of abnormal finishes and compare like with like. No outcome data from date D or later may enter date D evidence. First-start candidate status is research-only; do not use realized target abnormal code as a pre-race eligibility input at serving time.
- B1 remaining: canonical sire/BMS ID crosswalk and date-scoped research input coverage, synthetic edge regression of unresolved/unknown start status; publish no training population before these checks. C3 remains separate. No production change.

prediction_safe=false; production_authorized=false.

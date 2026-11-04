# BRDB M6 / P1-4 — 事前取得証跡ゲート監査（2026-11-04）

## Scope and decision

**P1-4 detection/gating implementation: PASS. Historical predictive as-of cohort: HOLD (0 attested entries).**

The input is the accepted research-only P0-2 2016–2025 result mart. The mart's selected pedigree snapshot is marked `STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED`. Neither this flag nor a caller-supplied observation date proves that a feature was already distributed before the scheduled race. The gate **does not** update BRDB CURRENT, the frozen Blood Review contract, RaceNote, PWA or forecasting logic.

## Fixed input and environment

- Fixed P0-2 mart SHA-256: `8b41f4b7132bc268428133535cce9c4aff79ac5b7b4c0dca5a5cdd5c1df13b63`.
- DuckDB `1.1.3`, 22-column P0-2 research mart, keys `race_key` and `horse_no`.
- Private execution in ChatGPT runtime. Only aggregate counters, source code and synthetic fixtures may enter the GitHub repository; licensed JRDB per-horse or per-race rows stay private.
- Independent historical 2026 UKC history Reader v0.4 is **not** a substitute for 2016–2025 historic observed source snapshots; its 2026 availability dates are later than the races under study.

## Full 2016–2025 audit results

| Year | Entries | Normal finishers | Static-only pedigree | No pedigree |
|---:|---:|---:|---:|---:|
| 2016 | 50,076 | 49,697 | 50,076 | 0 |
| 2017 | 49,299 | 48,922 | 49,299 | 0 |
| 2018 | 48,618 | 48,199 | 48,618 | 0 |
| 2019 | 47,574 | 47,118 | 47,574 | 0 |
| 2020 | 48,282 | 47,876 | 48,282 | 0 |
| 2021 | 47,821 | 47,476 | 47,821 | 0 |
| 2022 | 47,220 | 46,840 | 47,220 | 0 |
| 2023 | 47,672 | 47,273 | 47,672 | 0 |
| 2024 | 47,181 | 46,752 | 47,181 | 0 |
| 2025 | 47,884 | 47,497 | 47,880 | 4 |
| **Total** | **481,627** | **477,650** | **481,623** | **4** |

- Pre-race pedigree availability **independently attested** from the accepted P0-2 schema: **0 entries**.
- P1-5 / P1-6 / P1-7 **predictive claims / selection / evaluation**: **blocked**, not failed statistically.
- Guard rejects mismatched input SHA, unexpected static temporal flag, unexpected year/date, missing identity, duplicate `(race_key,horse_no)` and empty/incomplete annual cohort.
- Synthetic tests: `test_audit_brdb_asof_eligibility.py`: **4 PASS** locally under DuckDB 1.1.3. Tests cover SHA tampering, key duplication, positive audit but zero admission, strict failure on attempted predictive promotion, same-day/after-date claims and unverified user assertions.
- The optional `--require-prediction-safe` mode exits **nonzero** on these inputs. Normal audit emits aggregate-only `asof_eligibility_audit.json` with `prediction_safe=false`.

## Exact admission requirements before P1-5 / P1-6 / P1-7 predictive validation

1. Obtain a legitimately accessible **historical pre-race source archive** for the *actual relevant 2016–2025 observation dates*, not a later annually-selected UKC snapshot.
2. Verify the original immutable archive's SHA-256/size, source provenance and item membership. Verify each horse's canonical ID, pedigree code/values and the target race identity using an explicitly contracted crosswalk. No horse-name-only matching.
3. Establish source availability **strictly prior to race**; for a day-granularity archive with unknown publication time, reject same-race-day observations. A user assertion or a `signed_source_attestation=true` field is not sufficient.
4. Reconcile updates: require the historical values as captured then; reject overwrites by later corrections. Exclude conflicted, missing, future and unverified rows without imputation.
5. Freeze an immutable **eligible as-of cohort** and input manifest/lineage/hash and report its coverage separately from static coverage. Only this frozen cohort may feed a new predictive evaluation.
6. Preserve separate research lane; no automatic production promotion even if retrospective performance is positive.

## M6 stage gates

| Stage | Deliverable | Current decision |
|---|---|---|
| **P1-4** | Source provenance inventory, conservative as-of gate and audit | **Audit PASS; eligibility 0 / HOLD** |
| **P1-5** | Race/horse/year dependence-aware uncertainty on a frozen eligible cohort | **BLOCKED for predictive conclusion** |
| **P1-6** | Predetermined rolling train/validation/test windows; no train/test identity leakage | **BLOCKED for predictive conclusion** |
| **P1-7** | Incremental value over frozen non-blood baselines; calibrated held-out metrics | **BLOCKED for predictive conclusion** |

Static research P1-3 is still valid as an exploratory, not as-of-proven analysis: its final BH-adjusted pass count is 0. Even if independently attested historical sources become available, that prior null result does not authorize skipping multiplicity, dependency, robustness or comparison against real baselines.

## Local reproduction

```sh
python horse-racing/brdb/src/audit_brdb_asof_eligibility.py \
  --mart <PRIVATE_P0_2_MART_PARQUET> \
  --mart-sha256 8b41f4b7132bc268428133535cce9c4aff79ac5b7b4c0dca5a5cdd5c1df13b63 \
  --out <PRIVATE_OUTPUT_DIR>

python -m unittest discover -s horse-racing/brdb/tests \
  -p 'test_audit_brdb_asof_eligibility.py' -v
```

Output is the aggregate-only JSON `asof_eligibility_audit.json`. **Neither the 2016–2025 historical row-level mart nor the 2026 history ZIP is submitted to public GitHub Actions.**
## Committed-source synthetic CI acceptance

- GitHub source commit: `166cda67989a951314efdad686a7c1a097a81ece` (source/test/docs at test time).
- [Fallback Issue #2371](https://github.com/yukki0113/GPT/issues/2371) — `DATA_STORAGE_FALLBACK_RESULT status: PASS`, closed.
- [Actions run #41763353407](https://github.com/yukki0113/GPT/actions/runs/41763353407) — `run` job `completed/success`; DuckDB `1.1.3`, PyArrow `25.0.1`; artifact `data-storage-fallback-41763353407` available.
- Local aggregate-only audit JSON SHA-256: `8ce3992dd4f26416ae347a5c28a19eb2bd7fb04b0be25173ccca437bd7a1f4ec`; no licensed row data uploaded to GitHub.

**Gate acceptance = PASS (conservative exclusion). M6 predictive acceptance = HOLD (0 as-of-attested rows).**

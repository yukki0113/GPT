# JRDB Work INBOX 20260901-001

```text
request_id: JRDB-WORK-20260901-001
issued_at: 2026-09-01 JST
controller_role: JRDB independent-index design / methodological governance
work_role: implementation / Git / Actions / real-data audit
required_outbox_filename: JRDB_Work_OUTBOX_20260901_001.md
optional_artifact_manifest: JRDB_Work_ARTIFACTS_20260901_001.md
```

## 1. Objective

Continue the JRDB PWA independent-index implementation from the exact current GitHub `main` state.

The immediate objective is to complete **official RunPerf v0.1 materialization** so Ability development can consume a single audited historical RunPerf table with strict as-of coefficient provenance.

Do not redesign RunPerf. The official frozen specification is:

```text
candidate       = T1|EXPANDING|RAW
family          = T1
baseline_method = EXPANDING
time_variant    = RAW
```

The 2024-2025 RunPerf frozen holdout has already completed with `PASS_STRONG`.

## 2. Canonical Git state to read first

Repository:

```text
yukki0113/GPT
```

Read latest `main`, not a remembered SHA.

Required documents/files:

```text
horse-racing/jrdb/README.md
horse-racing/jrdb/docs/Work_Library_Exchange_Protocol_v0_1.md
horse-racing/jrdb/docs/JRDB_PWA_Index_Design_v0_1.md
horse-racing/jrdb/docs/JRDB_PWA_Index_Feature_Registry_v0_1.md
horse-racing/jrdb/docs/RunPerf_v0_1.md
horse-racing/jrdb/docs/RunPerf_Development_Decision_v0_1.md
horse-racing/jrdb/docs/RunPerf_Holdout_Protocol_v0_1.md
horse-racing/jrdb/docs/README_build_jrdb_runperf.md
horse-racing/jrdb/schema/jrdb_runperf_schema_v0_1.sql
horse-racing/jrdb/schema/jrdb_official_runperf_schema_v0_1.sql
horse-racing/jrdb/src/build_jrdb_runperf_features.py
horse-racing/jrdb/src/fit_jrdb_runperf_coefficient_snapshot.py
horse-racing/jrdb/src/audit_jrdb_runperf.py
```

Also inspect all current related tests/workflows before implementation.

## 3. Starting state

Already completed and accepted:

1. JRDB Index Base 2010-2025 real-history build/audit
2. RunPerf candidate-feature DB 2010-2025 build/audit
3. 84-candidate development comparison over 2013-2023
4. Frozen provisional selection before holdout
5. One-shot 2024-2025 holdout
6. Holdout classification `PASS_STRONG`
7. Official specification document `RunPerf_v0_1.md`
8. Initial official materialization schema `jrdb_official_runperf_schema_v0_1.sql`

The official-materialization schema exists, but the materializer / audit / full real-history execution are not yet complete.

## 4. Required task A — official RunPerf materializer

Implement a builder, expected path:

```text
horse-racing/jrdb/src/build_jrdb_official_runperf.py
```

The builder must consume the audited RunPerf candidate-feature SQLite and produce the official RunPerf SQLite defined by `jrdb_official_runperf_schema_v0_1.sql`.

### Required scoring chronology

For model year Y:

```text
snapshot(Y) <- coefficient fitting pairs whose target year <= Y-1
```

Examples:

```text
2013 rows <- snapshot fitted through 2012
2014 rows <- snapshot fitted through 2013
...
2024 rows <- snapshot fitted through 2023
2025 rows <- snapshot fitted through 2024
```

For 2010-2012 warm-up history used by the 2013 Ability fold:

```text
use the 2013 snapshot fitted through 2012
score_provenance = explicit warm-up retrospective provenance
```

Do not backfill later coefficient snapshots into earlier rows.

### Required official score

```text
MarginScore = -margin_per_1000m_sec
RunPerfRaw = intercept
           + beta_time * time_residual_raw_bias_sec
           + beta_margin * MarginScore
```

Higher is stronger.

### Required row provenance

At minimum preserve:

```text
race_key
race_date
year
horse_no
horse_id
source_calculation_status
score_status
expected_time_sec
day_bias_raw_sec
time_raw_bias_sec
margin_score
runperf_raw
coefficient_snapshot_target_year
coefficient_asof_through_year
coefficient_intercept
coefficient_beta_time
coefficient_beta_margin
score_provenance
```

Rows excluded upstream must remain visible with explicit status; do not silently drop or zero-fill them.

## 5. Required task B — audit

Implement an official RunPerf audit, expected path:

```text
horse-racing/jrdb/src/audit_jrdb_official_runperf.py
```

Audit at least:

- SQLite integrity
- one business row per race_key x horse_no
- row count reconciliation with EXPANDING source rows
- scored vs excluded counts by year/status
- `runperf_raw` arithmetic recomputation
- coefficient snapshot target year / as-of year chronology
- warm-up provenance rule
- no later-year snapshot written backward
- coefficient finiteness
- source component finiteness for scored rows
- market/odds/popularity fields absent
- stable horse/date ordering checks needed for Ability history consumption
- 2024 and 2025 coefficients reproduce the official RunPerf v0.1 documented snapshots within reasonable floating tolerance

Fail closed on chronology/provenance violations.

## 6. Required task C — tests

Add regression tests for builder and audit.

Minimum cases:

1. normal annual snapshot scoring
2. 2010-2012 warm-up retrospective scoring
3. no future coefficient backfill
4. excluded source row remains explicit and unscored
5. arithmetic matches frozen equation
6. invalid/non-finite snapshot fails
7. duplicate business key fails
8. market columns are absent / not consumed

Run existing relevant Index Base and RunPerf regression tests as well.

## 7. Required task D — real-history workflow

Add or extend a GitHub Actions Issue workflow to execute:

```text
JRDB Raw 2010-2025
 -> Index Base
 -> Index Base audit
 -> RunPerf feature DB (EXPANDING is sufficient for official materialization)
 -> RunPerf audit
 -> Official RunPerf materialization
 -> Official RunPerf audit
 -> lightweight result
 -> artifact upload
 -> Issue comment
```

Use the existing JRDB authenticated history-download pathway rather than moving annual ZIPs through chat.

The workflow result must distinguish:

- technical execution status
- data/audit gate status

A technically successful workflow with failed audit must not be reported as success.

## 8. Required task E — run real 2010-2025 audit

Execute the workflow on real JRDB 2010-2025 history.

Acceptance gates:

```text
Index Base gate = PASS
RunPerf feature gate = PASS
Official RunPerf gate = PASS
no chronology violations
no arithmetic violations
no duplicate official business keys
no market-input contamination
2024/2025 official snapshot coefficients match RunPerf_v0_1.md
```

Record annual scored/excluded counts and overall official RunPerf coverage.

Do not change the RunPerf specification to make the audit pass.

## 9. Conditional task F — prepare Ability foundation only after A-E pass

If and only if official RunPerf materialization passes real-history audit, begin the next infrastructure step without tuning an Ability model yet.

Create a design/schema proposal or minimal implementation for an **Ability pre-race feature snapshot foundation** that can later support:

```text
recent_performance
peak_performance
peak_gap
performance_stability
surface_fit
distance_fit
course_fit
going_fit
jockey_general_effect
jockey_surface_effect
weight_relative
sample-count / neff / missing flags
```

Important:

- use official materialized RunPerf as historical target/material
- strict as-of joins
- no odds/popularity
- no current-result leakage
- no same-day future-result leakage
- do not start feature/model selection on 2024-2025 unless a later Controller INBOX explicitly authorizes the Ability evaluation protocol

For this package, it is acceptable to stop after schema/data-contract groundwork once A-E are complete.

## 10. Hard constraints

Do not:

- redesign T1|EXPANDING|RAW
- rerank RunPerf candidates
- retune DayTrackBias on 2024-2025
- add carried weight to RunPerf
- replace explicit structural exclusions with imputation
- use odds/popularity as RunPerf/Ability/Edge inputs
- call 2024-2025 an untouched Ability holdout without Controller approval
- store only an opaque official score without components/provenance

2025 known fallback race contexts remain explicit structural exclusions unless a separate evidence-based parser/data-source correction is discovered. Do not fill them by guess.

## 11. Autonomous decisions allowed

Work may autonomously:

- choose implementation structure and function boundaries
- add indexes/performance improvements without semantic changes
- add audit checks
- fix clear technical defects with evidence
- create GitHub Issues/workflows needed to complete this package
- update operational README/status docs

If a methodological change is required, stop that branch of work and record it in OUTBOX under `controller_decisions_requested`.

## 12. Required OUTBOX

At completion or block, generate:

```text
JRDB_Work_OUTBOX_20260901_001.md
```

and make it available through File Library.

It must contain the fields required by `Work_Library_Exchange_Protocol_v0_1.md`, plus:

- exact real-history official RunPerf coverage
- annual status counts
- coefficient/provenance audit summary
- GitHub Issue/run/artifact identifiers
- all commit SHAs
- whether task F was started/completed
- recommended next Controller decision

If multiple generated artifacts matter to the Controller, also create:

```text
JRDB_Work_ARTIFACTS_20260901_001.md
```

## 13. Communication rule

Do not rely on the Work conversation alone as the handoff. The OUTBOX is mandatory.

When the package finishes, the user should be able to return to the Controller thread and say only:

```text
Workの001が完了しました。Libraryを確認してください。
```

The Controller will locate the OUTBOX by request ID and continue from it.
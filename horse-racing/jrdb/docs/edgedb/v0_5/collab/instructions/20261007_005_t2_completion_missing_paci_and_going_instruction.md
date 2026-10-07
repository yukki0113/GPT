# 20261007_005 — EdgeDB v0.5 Turn 2 Completion: Missing PACI + Going

Status: TODO
Date: 2026-10-07
Design authority: ChatGPT
Execution worker: Codex
Production impact: NONE

## Objective

Complete Turn 2 of the 2026 historical blind replay by closing the two known gaps in the merged partial freeze:

1. recover the five PACI dates that were omitted by the bulk `gdown --folder` transfer;
2. restore T6 `going_bucket` using the same isolated historical track-condition semantics that were used when the 2024-2025 v0.5 discovery mart was built.

Do not start Turn 3.

The target outcome is a new immutable 2026 pre-race match freeze covering all canonical PACI / SED dates currently available through 2026-10-04.

---

## Current partial Turn 2 baseline

Merged PR:

- PR #1895
- merge commit:
  `b99ba1ea64e70b9e374bba8793dd343e28d3cb67`

Current partial freeze:

- PACI days matched: 79
- races: 2,502
- runners: 34,550
- match rows: 11,427
- unique matched runners: 10,019
- current pre-race fact SHA:
  `526516f9e5a1f46d96de6484e68a9b04237f6f5d6ac2f80f0c34ad380e5ef5c0`
- current match SHA:
  `fbc6258626e9f407990639b1bcb3cfaad3b7d83666aee418c754d74f79240cf4`

This partial freeze is valid for the 79 matched dates, but it is superseded if this completion task succeeds.

Turn 1 cohort remains immutable:

- candidate count: 1,620
- cohort SHA:
  `a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9`

Do not regenerate or alter candidate membership.

---

# 1. Recover the five PACI dates by exact Drive file ID

The five files are confirmed to exist in the canonical PACI Drive folder and are individually downloadable.

Canonical folder:

`1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`

Exact missing files:

| Race date | Filename | Drive file ID |
|---|---|---|
| 2026-05-10 | PACI260510.zip | `1qwWppnmLWpSqN-479u5yISRp8yQjq_RX` |
| 2026-05-16 | PACI260516.zip | `1AMaONXFE-9JUDcb4Lzrmm2RYyO1le3e5` |
| 2026-05-31 | PACI260531.zip | `1kg7qxyHFDkriJVEWLdIYK5652WDZw3PM` |
| 2026-08-01 | PACI260801.zip | `1kySK0AycsjHSmJn4HVbaGuYkb-2mqYf7` |
| 2026-10-03 | PACI261003.zip | `1JnPqDp3u8D4Wql3bVNeWScQ9E6hw6nyO` |

The prior omission was a bulk-download transport failure, not source absence.

### Required workflow change

Keep the existing folder download for convenience, but after it completes:

1. enumerate expected PACI filenames from the canonical Drive inventory / SED date set;
2. detect missing local PACI files;
3. fetch known missing files by exact file ID;
4. fail closed if any canonical date is still absent.

Do not silently accept 79/84 coverage after this change.

The workflow must report:

- folder inventory count;
- bulk downloaded count;
- exact-ID recovered count;
- final PACI count;
- remaining missing date count.

Expected final remaining missing date count:

`0`

unless the canonical source changes after this instruction.

---

# 2. Going semantics: use the existing v0.2 historical exception

The 2024-2025 T6 discovery was not based on a PACI-native going field.

Canonical precedent:

`horse-racing/jrdb/src/build_jrdb_edge_feature_mart_v0_2.py`

That module explicitly documents:

> Historical track condition is the explicit exception: it is read first from
> `race_result_context` (SED-derived race context) into an isolated race-level
> snapshot, then result labels are joined in a separate query.

The implementation reads only:

```sql
SELECT race_key, track_condition_code
FROM race_result_context
```

and converts it with:

`jrdb_edge_v02_canonical.track_condition_bucket`

This is the semantic contract that Turn 2 must reproduce.

## Important scientific interpretation

This is not permission to use result outcomes for matching.

Track condition is a race-context variable that was already accepted as the one historical-source exception in the canonical Feature Mart.

For Turn 2, extract only the race-level condition:

- race_key
- track_condition_code

from the canonical 2026 SED/result-context source.

Do not read or pass through:

- finish
- abnormal result
- final odds
- popularity
- win payout
- place payout
- result IDM
- result performance fields
- any runner outcome field

The extraction step should be isolated before matcher input creation, just as in v0.2.

---

# 3. Derive 2026 going bucket with canonical mapping

Reuse the existing function:

`jrdb_edge_v02_canonical.track_condition_bucket`

Do not duplicate or invent a new mapping.

Expected buckets for v0.5:

- `GOOD`
- `SOFT_OR_WORSE`

Do not infer going from:

- weather;
- heavy-track suitability;
- PACI horse attributes;
- previous-race conditions.

It must come from the isolated race-level `track_condition_code`.

---

# 4. Race-level consistency audit

Because going is race context, enforce:

For every `race_key`:

- exactly one canonical non-conflicting track condition;
- all runners in that race receive the same `going_bucket`.

If SED contains multiple runner rows:

- collapse by race_key;
- verify identical `track_condition_code`;
- fail closed on conflicting nonblank values.

Report:

- race keys with going;
- race keys UNKNOWN;
- conflict count.

Expected conflict count:

`0`

Do not silently choose min/max/first on conflict.

---

# 5. Preserve result-blind matcher boundary

The matcher fact allowlist may now include:

- going_bucket

but must still exclude every result/market field.

Keep automated leakage tests.

The final fact mart may contain:

- identity
- venue
- surface
- distance
- frame
- sire
- transitions
- FIRST flags
- going_bucket

It must not contain:

- finish
- result rank
- popularity
- odds
- payout
- result hit
- post-race score
- result IDM
- any settlement field

---

# 6. Full 2026 chronology remains unchanged

Use the already accepted chronology design:

- 2010-2025 accepted Warehouse;
- strictly earlier 2026 starts;
- target row excluded;
- future rows excluded;
- missing/ambiguous history -> UNKNOWN;
- chronology violations must remain zero.

Recovering the five PACI dates should also improve later 2026 transition / FIRST derivation where those starts previously existed only as unresolved SED chronology.

Recompute all history-derived fields from scratch after all 84 PACI files are present.

Do not patch only the five dates into the old match table.

---

# 7. Rebuild the complete pre-race fact population

Run the full Turn 2 builder from scratch with:

- immutable 1,620 cohort;
- all available canonical PACI dates;
- canonical 2026 SED chronology;
- accepted 2010-2025 Warehouse;
- isolated race-level going snapshot.

Expected coverage target based on the current source snapshot:

- first date: 2026-01-04
- latest date: 2026-10-04
- PACI days: 84
- SED chronology days: 84
- missing PACI dates: 0

Do not hardcode expected race/runner counts.

Derive and report the actual totals.

---

# 8. Re-run all 1,620 exact-condition matches

Recompute the match freeze completely.

T6 must now participate.

Report family match counts including:

- T1
- T2
- T3
- T4
- T5
- T6

The previous partial run had no T6 matches because going was UNKNOWN for every fact.

A successful completion should therefore normally produce nonzero T6 matches if frozen T6 candidates encounter matching 2026 race conditions.

Do not require an arbitrary minimum T6 count; just report exact results.

---

# 9. New fingerprints supersede the partial freeze

Generate fresh:

- pre-race fact SHA-256;
- full match SHA-256;
- daily fact fingerprints;
- daily match fingerprints;
- PACI input-set fingerprint;
- isolated going snapshot fingerprint.

The merged partial fingerprints:

- fact `526516f9...`
- match `fbc62586...`

must be recorded as `SUPERSEDED_PARTIAL`, not overwritten without provenance.

---

# 10. Required tests

Retain all existing 20 tests and add focused tests for:

1. exact-ID fallback recovers a file omitted by bulk transfer;
2. remaining canonical PACI date mismatch fails closed;
3. track condition snapshot reads only race key + condition code;
4. canonical `track_condition_bucket` mapping is reused;
5. all runners in one race receive same going bucket;
6. conflicting going codes fail closed;
7. missing going remains UNKNOWN and does not match T6;
8. T6 GOOD exact match;
9. T6 SOFT_OR_WORSE exact match;
10. result fields cannot enter matcher fact schema;
11. full rerun deterministic fingerprints.

Minimum expected total tests after this addendum:

`31`

If implementation structure supports more, that is fine.

---

# 11. Required artifact outputs

Produce a new Actions artifact containing at least:

- `v05_2026_pre_race_facts.parquet`
- `v05_2026_match_freeze.parquet`
- `v05_2026_match_freeze_manifest.json`
- `v05_2026_match_freeze_audit.json`
- `v05_2026_match_counts_by_day.csv`
- `v05_2026_match_counts_by_family.csv`
- `v05_2026_going_snapshot.csv` or Parquet
- PACI input inventory / fingerprint

Keep row-level files out of Git.

---

# 12. Durable Git outputs

Update:

`horse-racing/jrdb/config/edgedb/v0_5/frozen/v05_2026_match_freeze_manifest.json`

Update the Turn 2 result report or add a completion report under:

`horse-racing/jrdb/docs/edgedb/v0_5/collab/results/`

Preferred completion report:

`20261007_006_2026_pre_race_match_freeze_completion_result.md`

The report must state clearly:

- prior 79-day partial freeze;
- exact five recovered PACI files;
- going-source exception parity with v0.2;
- final date coverage;
- new fingerprints;
- previous partial fingerprints superseded.

---

# 13. Acceptance recommendation

Return one:

- `READY_FOR_TURN3_OUTCOME_JOIN`
- `PARTIAL_PRE_RACE_COVERAGE`
- `GOING_CONTEXT_BLOCKED`
- `EXECUTION_BLOCKED`

Use `READY_FOR_TURN3_OUTCOME_JOIN` only if:

1. all canonical PACI dates in the current 2026 source set are present;
2. PACI date set equals canonical SED chronology date set;
3. going is resolved or explicitly UNKNOWN only where the canonical race-level condition itself is unavailable;
4. no result/market outcome fields enter matching;
5. all 1,620 candidates are consumed;
6. T6 is actually evaluated;
7. chronology violations are zero;
8. full freeze fingerprints are emitted;
9. artifact is immutable;
10. production remains unchanged.

---

# 14. Turn 3 remains forbidden

Do not:

- join finish positions;
- calculate 2026 ROI;
- join popularity or odds;
- assign OOS success/failure labels;
- prune candidates;
- change the 1,620 cohort;
- start density-based filtering decisions;
- modify current_manifest;
- publish v0.5.

Stop after the completed Turn 2 match freeze and return it for ChatGPT audit.

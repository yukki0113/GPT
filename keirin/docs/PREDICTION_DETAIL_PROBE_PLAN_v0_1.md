# KEIRIN Prediction Detail Probe Plan v0.1

Date: 2026-09-23
Purpose: Determine the minimum additional Historical retrieval required for prediction-grade Canonical.

## 1. Probe philosophy

Do not bulk-fetch race details immediately.

Use a tiny representative sample to answer:
- what official transition exposes rider-level Historical snapshot data
- what result fields are available
- whether comments are available
- whether a published line/並び representation is available
- whether the same structure holds across eras

Only after this is known should request volume be calculated.

## 2. Representative sample

Minimum sample:
- 2016: one ordinary male standard race
- 2020: one ordinary male standard race
- 2025: one ordinary male standard race
- 2025: one Girls race if available

If a special no-line male ruleset exists in the acquired period, sample one separately.

Prefer mid-card ordinary races rather than finals only.

## 3. What to inspect

### PRE rider facts
For every starter, test availability of:
- rider_id
- car_no / frame_no
- historical rider name
- age
- prefecture / region
- training term
- class
- leg style
- gear ratio
- competition score
- win/top2/top3 rates
- 1st/2nd/3rd/outside counts
- S/H/B
- nige/makuri/sashi/mark tendency
- recent-race display

### PRE tactical facts
Test:
- rider comments
- expected formation
- line order
- line grouping
- solo
- contest/競り
- any source-updated timestamp

### POST facts
Test:
- finish order
- kimarite
- B/S markers
- time
- margin
- disqualification/withdrawal
- payouts
- popularity

## 4. Line evidence classification

For each sampled race, assign one:
- L0: no line representation found
- L1: human-readable text only
- L2: structured line/order data directly present in source
- L3: structured plus rider comments supporting formation

Do not call L0 a failure of the whole project.
P0/P1 prediction research can proceed without line.

## 5. Retrieval cost estimate

Before any bulk acquisition, calculate:
- requests per race
- bytes per race
- total races
- projected requests for 2016-2025
- projected bytes
- projected wall-clock at 3s/request
- cache/refetch behavior

Decision gate:
If one request can return all riders + result for a race, prefer that.
Avoid one request per rider unless no alternative exists and explicit review approves it.

## 6. Era stability audit

For each field, record:
- 2016 present/absent
- 2020 present/absent
- 2025 present/absent
- field name/path differences
- semantic differences

A field becomes Canonical mandatory only if semantics are stable or normalization is explicitly versioned.

## 7. Probe output

Write:
- `keirin/docs/PREDICTION_DETAIL_PROBE_RESULT_<date>.md`
- machine-readable JSON audit
- sample Raw saved under immutable detail-raw path
- exact request contract
- recommended bulk acquisition plan
- fields approved for Canonical
- line evidence level
- comments evidence level

## 8. Stop conditions

Stop and report, do not bulk-fetch, if:
- access restriction / 403 / 429 appears
- endpoint requires circumvention
- Historical page silently substitutes current-profile values
- result data cannot be separated temporally from pre-race snapshot
- request volume is materially higher than expected

## 9. Expected decision after probe

Possible outcomes:

A. KEIRIN.JP exposes entry + result + published line
- proceed with full Prediction Canonical

B. KEIRIN.JP exposes entry + result but not line
- build P0/P1 first
- research an approved separate source or inference pipeline for line

C. KEIRIN.JP exposes only partial entry
- retain Core Canonical
- assess additional approved source before bulk acquisition

D. Historical semantics unstable by era
- split parser by era but map to one Canonical contract with explicit provenance

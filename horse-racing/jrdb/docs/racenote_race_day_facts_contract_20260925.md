# RaceNote Race-day Facts Pre-Freeze Contract

Date: 2026-09-25

## Purpose

Target-race weather and track condition may materially change scenario context,
but result-derived JRDB data must never flow backward into the pre-Freeze
forecast.

This contract provides a narrow, provenance-aware path for independent
pre-result race-day facts.

## General Evidence contract

```text
race_data_context.race_day_facts
  status
  source_kind
  as_of
  weather
  track_condition
  policy
```

AVAILABLE requires an explicitly independent input. Missing input remains
UNAVAILABLE and is never interpreted as negative evidence.

Policy:

```text
result_independent_required = true
may_auto_rank = false
missing_is_not_negative_evidence = true
```

## Ingress validator

Module:

```text
horse-racing/jrdb/src/racenote_race_day_facts.py
```

Accepted input keys:

```text
source_kind
as_of
weather
track_condition
result_independent
```

Requirements:

- `result_independent == true`
- non-empty `source_kind`
- timezone-aware ISO `as_of`
- at least one of `weather` or `track_condition`
- unknown fields fail closed
- target view must already be `INDEPENDENT`

The validator does not create a rank or probability adjustment.

## Prepare workflow

`.github/workflows/racenote_gen0_3_realdata_prepare.yml` accepts optional:

Issue request:

```json
{
  "race_day_facts": {
    "source_kind": "JRA_OFFICIAL_PRE_RACE",
    "as_of": "2026-09-27T09:30:00+09:00",
    "weather": "雨",
    "track_condition": "重",
    "result_independent": true
  }
}
```

Manual workflow dispatch:

```text
race_day_facts_json
```

Injection order:

```text
source RaceNote bundle
-> Independent Firewall
-> race-day facts validator / attacher
-> RaceReview adapter
-> General Evidence
-> Synthesis
```

This order prevents the race-day path from bypassing the existing market /
current-JRDB / Training-Edge firewall.

## Smoke verification

### No facts

Issue #1382  
Run `36113627936`

```text
status = PASS
race_day_facts_status = UNAVAILABLE
race_day_facts_source_kind = null
```

### Safe transport fixture

Issue #1381  
Run `36113540839`

The injected values were explicit test fixture strings, not historical claims.

```text
status = PASS
race_day_facts_status = AVAILABLE
race_day_facts_source_kind = TEST_FIXTURE
```

The workflow step `Attach independent race-day facts` completed successfully.

## Commits

```text
25f235b6a33749eba4cb047208a29f7f7e4fb147
  General Evidence race-day facts receptacle

691aec32830879b9f9f78e3b76da5d3bcef7a274
  Race-day facts validator / attacher

a6a033660e001ed6c8db7178aeaa84ed1267d43b
  Validator unit tests

949c2d32e53edf4284ee13edb2410b9b94654b13
  Gen0.3 Prepare workflow wiring
```

## Official source candidate

JRA states that race-day weather and track condition are published in current
meeting information, and track information is published before and during race
days.

Automatic acquisition must:

1. use JRA pre-result pages only;
2. identify the venue from page content, not from a fixed index number;
3. capture source publication/as-of time;
4. refuse to attach if the source timestamp cannot be proven pre-result;
5. never fall back to ZED or another result-derived source;
6. keep the facts as context only until repeated blind validation justifies any
   stronger use.

Next implementation target: a fail-closed JRA track-information parser.

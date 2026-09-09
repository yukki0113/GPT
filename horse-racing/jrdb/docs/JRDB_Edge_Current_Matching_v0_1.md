# JRDB Edge Current Matching v0.1

Status: **IMPLEMENTED / SHADOW USE**
Established: 2026-09-09

## 1. Purpose

JRDB Edge Registryで検証済みの再利用可能Edgeを、開催前の当日出走馬へleakage-safeに照合する共通経路を定義する。

この経路はPWA新聞、RaceNote/GPT、独自指数のEdge表示層から共用できるconsumer-neutralな入力・出力契約とする。
Phase1ではEdge一致を表示・分析へ供給するだけで、Abilityや最終指数へ自動加点しない。

## 2. Canonical flow

```text
PACIyymmdd.zip
  ├─ BAC: current race context
  ├─ KYI: current runner + exact prev1 link
  └─ UKC: horse pedigree/profile when present
        |
        v
build_jrdb_edge_current_facts.py
        |
        +-- optional Analysis Lite v1.2
        |      └─ exact KYI prev_race_key_1 + horse_id lookup only
        |
        v
canonical current runner fact JSONL
        |
        v
jrdb_edge_matcher.py
        |
        v
consumer-neutral edge_matches[]
```

The one-command entry point is:

`src/run_jrdb_edge_match_current.py`

## 3. Source policy

Current-race source is pre-race PACI only.

Allowed current-race facts:

- BAC race context
- KYI runner identity / frame / jockey / trainer / previous-race link
- UKC pedigree/profile contained in the pre-race PACI
- Analysis Lite history strictly before target race date

Forbidden current-race facts:

- SED result
- final odds / final popularity
- finish / payout
- confirmed post-race track state
- any record dated after the target race

Current SED must never enter an Edge condition.

## 4. Exact previous-race resolution

TRANSITION features never search for a merely plausible recent history row.

Resolution requires both:

1. KYI `prev_race_key_1`
2. the same `horse_id`

The matching Analysis Lite row must also satisfy:

`previous_race_date < target_race_date`

If the exact link is absent, ambiguous, same-day, or future-dated, the implementation does not guess a substitute previous run.

## 5. Degraded operation

Analysis Lite is optional.

When no history source or exact previous row is available:

- COURSE features remain available.
- PEDIGREE features remain available when an as-of UKC profile exists.
- HUMAN features based on current KYI codes remain available.
- TRANSITION derived fields become null.
- an Edge requiring a null TRANSITION field therefore does not match.

The whole runner is not discarded only because previous history cannot be resolved.

## 6. Shared canonical derivations

Historical Feature Mart and current matching share:

`src/jrdb_edge_canonical.py`

Canonical derivations include:

- `frame_zone`
- `distance_change_m`
- `distance_change_bucket`
- `surface_transition`
- `frame_transition`

This is required so Discovery-time buckets and Forward-time matching buckets cannot drift into separate implementations.

## 7. Matcher policy

Default eligible registry status:

`ACTIVE`

Additional statuses are opt-in through `--statuses`.

Supported statuses are currently:

- ACTIVE
- PROVISIONAL
- WATCH
- DECAYING

Expired Edges do not match.
Review-due Edges retain an explicit `review_due` evidence flag.

Condition matching is exact against the frozen canonical condition fields.
No fuzzy code coercion is performed.

## 8. One-command usage

```bash
python horse-racing/jrdb/src/run_jrdb_edge_match_current.py \
  --paci /path/to/PACI260912.zip \
  --analysis-db /path/to/jrdb_analysis_v1_2.sqlite \
  --registry-jsonl /path/to/edge_registry_active.jsonl \
  --output-jsonl /path/to/edge_matches.jsonl \
  --facts-jsonl /path/to/current_edge_facts.jsonl
```

To emit only runners with at least one match:

```bash
--only-matched
```

To explicitly include non-ACTIVE shadow statuses:

```bash
--statuses ACTIVE,PROVISIONAL,WATCH
```

Normal production/shadow consumption should keep the default `ACTIVE` unless a caller deliberately requests another status.

## 9. Output contract

Each output JSONL row is consumer-neutral:

```json
{
  "key": {
    "race_key": "...",
    "race_horse_key": "...",
    "horse_id": "...",
    "horse_no": 1,
    "race_date": "YYYY-MM-DD"
  },
  "edge_matches": []
}
```

Each match carries the Edge identity, polarity, status, strength/confidence where available, registry version, and evidence including the exact conditions that matched.

`--facts-jsonl` optionally preserves the canonical current runner facts used for the decision, allowing audit and downstream reuse.

## 10. Audit statuses in current facts

Current fact rows expose source-resolution status rather than silently filling gaps.

Examples:

- `profile_status = MATCHED`
- `profile_status = MATCHED_UNDATED`
- `profile_status = MISSING_ASOF`
- `previous_lookup_status = RESOLVED`
- `previous_lookup_status = NO_LINK`
- `previous_lookup_status = NO_HISTORY_SOURCE`
- `previous_lookup_status = LINK_NOT_RESOLVED`

A positively future-dated UKC profile is never selected.

## 11. Regression coverage

Regression tests cover:

- latest non-future UKC profile selection
- future-only profile rejection
- exact KYI previous link
- no guessed fallback history
- same-day/future previous-row rejection
- canonical transition bucket boundaries
- synthetic fixed-width PACI -> current facts -> Matcher
- COURSE survival when history is absent
- ACTIVE default and explicit status opt-in
- `--only-matched`
- output identity and optional facts JSONL

The tests are bridged into the existing JRDB Edge Registry V2 regression suite without modifying the protected workflow file.

2025-only V2 smoke baseline after current-fact integration:

- request: `current-facts-smoke-20260909-a`
- run_id: `34305527375`
- tests exit code: `0`
- all V2 pipeline exit codes: `0`
- integrity_check: `ok`

## 12. Related contracts

- `docs/JRDB_Edge_Contract_v0_1.md`
- `docs/JRDB_Edge_Registry_Phase1_v0_1.md`
- `src/build_jrdb_edge_current_facts.py`
- `src/jrdb_edge_canonical.py`
- `src/jrdb_edge_matcher.py`
- `src/run_jrdb_edge_match_current.py`
- `schema/jrdb_edge_publication_manifest_schema_v0_1.json`

This document describes the current matching transport and leakage policy. Edge discovery, validation thresholds, Registry lifecycle, and publication identity remain governed by their respective Phase1 contracts.

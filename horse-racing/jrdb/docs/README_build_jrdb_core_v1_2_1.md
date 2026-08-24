# JRDB Core Builder v1.2.1

`src/build_jrdb_core_v1_2_1.py` is an additive extension of Core v1.2.

It preserves the proven v1.1.2 normalization/duplicate logic and v1.2 UKC horse-profile enrichment, then adds two fields required by Analysis Lite v1.1.

## Added fields

### `entry.frame_no`

Source: KYI `枠番`

- human position: 324
- 0-based byte offset: 323
- length: 1

### `result.track_condition_code`

Source: SED `馬場状態`

- human position: 70
- 0-based byte offset: 69
- length: 2

These are added in `schema/jrdb_core_schema_v1_2_1.sql`.

## Reason for the patch

The existing Core `race.condition_code` is the BAC race condition/class field. It must not be interpreted as the actual track condition.

Analysis Lite v1.1 therefore consumes:

- `race.condition_code` as `race_condition_code`
- `result.track_condition_code` as actual `track_condition_code`
- `entry.frame_no` as `frame_no`

## Build strategy

1. run v1.1.2 normalization using the v1.2.1 additive schema;
2. run v1.2 UKC profile enrichment;
3. scan canonical KYI and SED members and backfill the two added dimensions;
4. set builder/schema metadata to `1.2.1-production` / `v1.2.1`.

The established v1.1.2 normalized fields are not rewritten by this patch.

## Regression requirement

Before promoting a newly built Core v1.2.1 as a durable production Core, compare all pre-existing normalized fields/counts against the accepted v1.2/v1.1.2 regression baseline. The only intended differences are the two new populated columns and metadata version identifiers.

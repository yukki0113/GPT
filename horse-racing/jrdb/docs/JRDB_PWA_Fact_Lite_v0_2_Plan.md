# JRDB PWA Fact Lite v0.2 implementation plan

## Requested search conditions

- year From / To
- month From / To
- venue
- turf / dirt / obstacle
- distance From / To
- track condition
- race name partial match
- minimum starts

Existing optional cross-filters for age / sex / popularity / running style are retained for now because they are already supported by the row-level Fact and do not block the requested UI. They can be hidden or reorganized later during final UI cleanup.

## Requested aggregation axes

- frame
- sire
- jockey
- running style
- age
- sex
- popularity
- distance extension / same / shortening
- previous class

Existing broodmare-sire aggregation is retained as an additional available axis until an explicit removal decision is made.

## Delivery order

1. Build and publish Fact Lite v0.2 first while keeping the current PWA UI compatible.
2. Verify v0.2 distribution and manifest.
3. Update the Fact Lite UI / query builder to schema v0.2.
4. Record iOS real-device timings.
5. Add race names to the upstream Analysis distribution and republish; until then the race-name input remains visibly unavailable rather than returning misleading zero results.

## Race-name boundary

JRDB BAC contains `race_name`, but current Analysis Lite v1.2 does not. Fact Lite v0.2 therefore supports two source capabilities:

- Analysis without `race_name`: all v0.2 functions except race-name search
- Analysis with `race_name`: `dim_race.race_name` is populated and partial-match search becomes active

No race name is inferred or sourced from unrelated data.

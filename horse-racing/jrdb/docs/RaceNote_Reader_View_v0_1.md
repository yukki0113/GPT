# RaceNote Reader View v0.1

## 1. Purpose

RaceNote final schema v1.0 is the authoritative GPT-facing observation bundle.  It intentionally preserves detailed PACI observations, Analysis Lite history, Stats Mart summaries, coverage metadata and provenance.

For a full field this produces a fairly large JSON document.  Reader View v0.1 is a **derived reading/transport projection** that reduces repeated JSON structure without changing the authoritative RaceNote semantics.

Reader View is not a new prediction model and is not a replacement source of truth.

```text
RaceNote v1.0 authoritative bundle
        |
        +--> Reader View v0.1
               - compact JSON
               - repeated context hoisted
               - reversible
               - semantic hash bound to source
```

## 2. Responsibility boundary

Reader View v0.1 MUST NOT:

- rank horses;
- produce scores or marks;
- recommend bets;
- remove observations because they appear unimportant;
- infer missing overseas history;
- change `as_of_exclusive` / leakage policy;
- replace `race_bundle_*.json` as the authoritative artifact.

Prediction logic remains outside RaceNote converter/router.

## 3. v0.1 transformation

Implementation: `src/racenote_reader_view.py`.

The source must be RaceNote schema v1.0.

The view performs only the following transformations.

### 3.1 Statistic shared context

When every statistic summary under horse `stats` and race `race_trends` carries the same values for all of:

- `period`
- `as_of_exclusive`
- `track_condition_scope`
- `source`

those four values are moved to:

```text
shared_context.stats
```

If even one statistic node is missing a field or has a different value, statistic context is not hoisted.

### 3.2 Historical profile shared context

When every non-null `historical_profile` carries the same:

- `source`
- `source_window_start`
- `as_of_exclusive`

those values are moved to:

```text
shared_context.historical_profile
```

A horse with `historical_profile = null` does not cause fake profile data to be generated.

If observed profiles disagree, the context stays on the individual profiles.

### 3.3 Compact serialization

Reader View is written as compact JSON by default.  Pretty output is debugging-only.

No `null`, list, observation, note or consumer-visible fact is dropped in v0.1.

## 4. Reversibility contract

Reader View stores:

```text
view_version = 0.1
source_schema_version = 1.0
source_semantic_sha256 = <canonical semantic hash>
```

`expand_reader_view()` reconstructs the source semantic bundle and verifies the semantic hash.

The semantic hash is calculated from UTF-8 JSON with sorted object keys and compact separators, so it is independent of whitespace and input key order.

A changed observation, missing value, or conflicting restored context must fail validation rather than silently produce a different RaceNote.

## 5. View policy metadata

v0.1 explicitly declares:

```json
{
  "lossless": true,
  "prediction_logic": false,
  "field_omission": false,
  "context_hoist": true
}
```

This policy is part of the reader artifact so GPT can distinguish a reversible reading projection from any future lossy summary.

## 6. Production packaging contract

When integrated into the Request Router, each requested race should retain both files:

```text
race_bundle_YYYYMMDD_開催NR.json
reader_view_YYYYMMDD_開催NR.json
```

- `race_bundle_*` remains authoritative.
- `reader_view_*` is the preferred first-read representation for GPT because it is smaller and still reversible.
- For audit, schema validation, unknown future consumers, or Reader View validation failure, use the authoritative bundle.

`request_manifest.json` should record, per view:

- view version;
- source bundle filename;
- reader view filename;
- source semantic SHA-256;
- round-trip validation status.

Reader View generation failure should fail the request while Reader View is declared lossless; silently emitting an unverifiable view would violate the contract.

## 7. Real-data PoC

PoC source: 2024-12-28 中山11R ホープフルS, 18 horses, production RaceNote v1.0.

Observed source file:

- pretty authoritative JSON: 264,682 bytes

Reader View prototype:

- compact Reader View: about 134.6 KB
- reduction versus current pretty artifact: about 49%
- `expand_reader_view()` semantic SHA validation: PASS

The reduction comes from JSON formatting and repeated context removal, not observation deletion.

## 8. Tests

`tests/test_racenote_reader_view.py` fixes these contracts:

1. uniform contexts are hoisted and exact source object is restored;
2. source bundle is not mutated;
3. mixed statistic context is left in place;
4. mixed historical-profile context is left in place;
5. null historical profile does not invent data and does not prevent valid non-null context hoisting;
6. tampering is detected by semantic hash;
7. unsupported RaceNote schema is rejected;
8. compact writer produces valid equivalent JSON.

The common JRDB/RaceNote CI compiles `racenote_reader_view.py` and runs these tests.

## 9. Future versions

A future view may explore more aggressive field selection or abbreviation, but that is **not v0.1**.

If information is intentionally omitted, the result must use a different version and explicitly declare at least:

- `lossless = false`;
- omitted field policy;
- intended reasoning use;
- fallback to authoritative bundle;
- comparison evidence that prediction quality is not degraded.

Do not quietly evolve v0.1 from reversible to lossy.

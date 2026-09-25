# RaceNote RaceReviewDB CURRENT Consumer Contract v0.1

Status: IMPLEMENTED  
Date: 2026-09-25

## 1. Purpose

RaceReviewDB v0.1 exposes a stable Google Drive consumer entrypoint:

- file: `RaceReviewDB_CURRENT.zip`
- stable file ID: `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`

RaceNote must consume that stable CURRENT instead of pinning an immutable
generation-specific ZIP.

The consumer path is:

```text
stable Drive CURRENT file ID
  -> download through repository Drive bridge
  -> ZIP validation
  -> safe extraction
  -> RaceReviewReader validation
  -> generation cache
  -> RaceNote RaceReview adapter
```

## 2. Resolver

Implementation:

- `src/racenote_racereview_current.py`

Resolver version:

- `RaceNote-RaceReview-Current-Resolver-0.1`

The resolver reuses:

- `tools/gpt_io/gdrive/gdrive_api.py`

It does not create a second Drive authentication implementation.

## 3. Validation gates

A downloaded CURRENT is accepted locally only after:

1. stable Drive file ID is resolved under the configured automation root,
2. file name is exactly `RaceReviewDB_CURRENT.zip`,
3. ZIP integrity test passes,
4. unsafe archive paths are rejected,
5. exactly one `current.json` is present,
6. `RaceReviewReader` accepts CURRENT status,
7. manifest validation_status is PASS,
8. current/manifest generation_id matches,
9. accepted generation is readable again after cache publication.

Any failure leaves the previous accepted local cache state unchanged.

## 4. Cache behavior

Accepted generations are cached under:

```text
<cache-root>/
  generations/
    <generation_id>/
  racereview_current_resolver_state.json
```

The local resolver state records:

- Drive file ID
- Drive name
- modified time
- size
- Drive MD5 when available
- downloaded ZIP SHA-256
- RaceReviewDB generation_id
- period_from / period_to
- Review schema / logic / baseline versions
- accepted local generation path

If the Drive fingerprint is unchanged and the cached generation re-validates
through `RaceReviewReader`, the download is skipped.

The stable Drive file may change bytes over time while keeping the same file ID.
The cache therefore keys acceptance to Drive metadata plus validated
RaceReviewDB generation identity, not to the file ID alone.

## 5. RaceNote adapter CLI

Normal operation:

```bash
python src/racenote_racereview_adapter.py \
  --independent-view <independent.json> \
  --racereview-current-cache <cache-dir> \
  --output <racereview_evidence.json>
```

The adapter resolves the operational Drive CURRENT automatically and records
resolver provenance in the sidecar source.

Audit / replay operation may instead use an already extracted immutable root:

```bash
python src/racenote_racereview_adapter.py \
  --independent-view <independent.json> \
  --racereview-root <extracted-generation-root> \
  --output <racereview_evidence.json>
```

The two source modes are mutually exclusive.

## 6. Identity and as-of boundary

This resolver does not change the RaceReview adapter's evidence contract.

RaceNote continues to use:

- `horse_id = JRDB blood_registration_no`
- no horse-name fallback
- `race_date < target_date`
- same-day Review excluded
- read-only RaceReviewDB access

The resolver handles artifact delivery only. It does not reinterpret Review
rows or prediction semantics.

## 7. Forecast boundary

RaceReviewDB remains a historical evidence source inside Independent Forecast.

It does not open:

- current JRDB consensus
- current market
- Edge Value
- RL / Value
- Training Edge
- target result

The Gen0.3 reading order remains:

```text
DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY
```

## 8. Operational ownership

RaceReviewDB owns:

- CURRENT publication
- generation validation
- stable Drive file replacement
- historical correction / replay policy

RaceNote owns:

- resolving accepted CURRENT for consumption
- historical evidence projection
- duplicate-evidence handling
- comparison / forecast / short-comment semantics

RaceNote must not mutate RaceReviewDB through the reader or resolver.

# BRDB CURRENT / Reader Contract v0.1

Status: IMPLEMENTED / OPERATIONAL FOUNDATION  
Date: 2026-10-22

## Purpose

BRDB consumers must not read pedigree Parquet relations directly.

The supported path is:

```text
BloodReviewDB_CURRENT.zip
        |
        v
current.json
        |
        v
manifest.json
        |
        v
immutable pedigree generation
        |
        v
BloodReviewReader
        |
        +-- horse_profile(horse_id)
        +-- parent_relations(horse_id)
        +-- lineage(lineage_code)
        +-- horse_pedigree(horse_id)
        +-- profiles_for_horses(horse_ids)
```

This contract exposes pedigree facts only. Blood Review scoring/interpretation is Phase 2.

## Current pointer

Machine-readable schema:

`schema/brdb_current_pointer_v0_1.schema.json`

Required v0.1 pointer:

```json
{
  "status": "CURRENT",
  "artifact_type": "brdb_pedigree",
  "generation_id": "<16-hex generation>",
  "manifest": "manifest.json",
  "reader_contract_version": "v0.1"
}
```

The pointer contains no horse data and does not duplicate manifest metadata.

## CURRENT bundle

Builder:

`src/build_brdb_current_bundle.py`

Stable operational filename:

`BloodReviewDB_CURRENT.zip`

Bundle layout:

```text
current.json
manifest.json
audit.json
pedigree_fact.parquet
parent_relation.parquet
pedigree_name_alias.parquet
lineage_code_master.parquet
```

The immutable generation remains the source generation. CURRENT is only a stable serving wrapper.

The bundle builder:

1. requires a PASS generation manifest;
2. copies only the fixed required generation objects;
3. writes `current.json`;
4. validates the staged root through `BloodReviewReader`;
5. writes ZIP members in deterministic order with fixed ZIP timestamps.

It does not mutate the immutable generation.

## Reader validation

Implementation:

`src/brdb_pedigree_reader.py`

Before any DuckDB query, the Reader verifies:

- `current.json.status == CURRENT`
- `artifact_type == brdb_pedigree`
- supported reader contract version
- current generation ID == manifest generation ID
- manifest `validation_status == PASS`
- supported schema version
- every required object exists
- every required object SHA-256 matches the manifest
- `parent_relation rows == pedigree_fact rows * 3`

Any failure is fail-closed.

## Identity policy

All horse queries require JRDB blood registration number `horse_id`.

Horse name is descriptive only.

There is no name lookup or name fallback.

Missing horse ID result:

- single query: `None`
- batch query: missing ID omitted from result map

This is consistent with the RRDB identity boundary.

## Reader v0.1 API

### horse_profile(horse_id)

Returns one canonical `pedigree_fact` row or `None`.

### parent_relations(horse_id)

Returns relation rows in order:

1. sire
2. dam
3. broodmare_sire

Unresolved relations are returned as facts with their resolution status. They are not guessed.

### lineage(lineage_code)

Returns one official JRDB lineage mapping row or `None`.

### horse_pedigree(horse_id)

Returns the stable consumer projection:

- horse ID/name/birth date
- sire name/year/lineage/relation
- dam name/year/relation
- broodmare sire name/year/lineage/relation
- field coverage
- generation/schema/builder/alias provenance

It does not expose Blood Review score because review logic is a separate future layer.

### profiles_for_horses(horse_ids)

Batch profile lookup with the same horse-ID semantics as the single lookup.

## Initial immutable generation

The first accepted generation is:

`eeca93556584a5b8`

It is externally persisted in the user-designated BRDB Drive location.

The generation manifest reports:

- pedigree_fact: 82,107
- parent_relation: 246,321
- pedigree_name_alias: 21
- lineage_code_master: 83
- validation_status: PASS

This generation remains immutable after CURRENT publication.

## Operational CURRENT publication

The first stable operational CURRENT file is now published:

- filename: `BloodReviewDB_CURRENT.zip`
- Drive file ID: `1fvqJgMMf1KUNL0Zr_GVnUAC6FyU8rMVz`
- generation: `eeca93556584a5b8`
- size: `6,923,691` bytes
- SHA-256: `c0eda6fc55472a4a7a327dcbee6498063bf19209285dfa0b4bc0284ba554305f`

Repository transport pin:

`config/public_drive/brdb_current_v0_1.json`

Resolver:

`src/brdb_current.py`

The resolver uses the repository's reviewed public Drive read-only transport. It:

1. verifies the transport manifest identity;
2. downloads only the pinned stable file ID;
3. requires exact size and SHA-256;
4. safely extracts the ZIP;
5. validates the extracted root through `BloodReviewReader`;
6. promotes only a fully validated generation into local cache;
7. never replaces an accepted cache after a failed refresh.

Resolver cache identity includes the reviewed transport-manifest SHA. A changed Git manifest therefore forces a fresh verification path.

### Drive permission hardening

At implementation time, Drive metadata reported the stable CURRENT object as publicly writable (`anyone: writer`).

This is not an integrity bypass because the repository pins exact SHA-256 and the resolver fails closed on byte changes, but it is an availability and source-governance risk.

Before normal operational use, change the BRDB Drive folder / CURRENT file general access to:

```text
Anyone with the link: Viewer
```

Do not make the artifact private while the public read-only transport is the operational download path.

## Tests

`tests/test_brdb_pedigree_reader.py` covers:

- valid CURRENT metadata
- current/manifest generation mismatch
- SHA-256 tampering
- parent relation cardinality
- horse_id-only projection
- deterministic CURRENT ZIP creation

`tests/test_brdb_current.py` covers:

- first resolve and validated cache hit
- failed/tampered refresh preserving accepted cache
- transport filename contract failure

These are lightweight contract tests and do not require the 2010-2025 raw rebuild.

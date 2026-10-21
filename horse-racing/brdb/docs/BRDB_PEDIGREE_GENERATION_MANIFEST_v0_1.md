# BRDB Pedigree Generation Manifest v0.1

Status: FOUNDATION CONTRACT  
Date: 2026-10-21

## Canonical locations

- Builder: `horse-racing/brdb/src/build_brdb_pedigree_generation.py`
- Pedigree and relation schema: `horse-racing/brdb/schema/brdb_pedigree_fact_schema_v0_1.sql`
- Manifest JSON Schema: `horse-racing/brdb/schema/brdb_pedigree_generation_manifest_v0_1.schema.json`
- Current guarded resolver: `horse-racing/brdb/src/brdb_parent_relation.py`
- Durable generation files: external immutable artifact storage, not Git

This contract describes the foundation pedigree generation. It does not authorize a production `CURRENT` pointer or a PWA/RaceNote serving cutover.

## Generation layout

```text
brdb-pedigree-generation-<generation_id>/
  manifest.json
  audit.json
  pedigree_fact.parquet
  parent_relation.parquet
  pedigree_name_alias.parquet
  lineage_code_master.parquet
```

`generation_id` is the first 16 lowercase hexadecimal characters of the SHA-256 of the JSON serialization of sorted `(archive_name, archive_sha256)` pairs. The builder uses `json.dumps(..., sort_keys=True)` before hashing. Input paths do not contribute to the identity. An existing generation directory is never overwritten.

The builder reuses the JRDB UKC fixed-width parser and the BRDB guarded resolver. It reduces observations by maximum `data_date` per `horse_id`; equal-date equal-`semantic_hash` observations collapse, while equal-date conflicting hashes fail. Every parent relation has its own status and unresolved IDs remain null. Runtime fuzzy matching is prohibited.

## Manifest fields

The JSON Schema above is the machine-readable contract. Required fields have these meanings:

| Field | Meaning |
|---|---|
| `artifact_type` | Fixed `brdb_pedigree`. |
| `generation_id`, `schema_version`, `builder_version` | Generation identity and producer versions. |
| `source_family`, `source_archive_count`, `source_min_data_date`, `source_max_data_date` | Source summary. Dates use `YYYYMMDD`. |
| `source_archives` | Archive name, exact byte size, and SHA-256 for each input ZIP. |
| `row_counts` | Validated rows in each of the four Parquet relations. |
| `canonical_keys` | `pedigree_fact(horse_id)` and `parent_relation(child_horse_id, role)`. |
| `alias_version`, `lineage_source_version` | Explicit alias and official lineage source versions. |
| `validation_status` | `PASS` only after all relation conversions and validations pass. |
| `output_sha256` | SHA-256 of each Parquet file and `audit.json`. `manifest.json` is not self-hashed. |

For v0.1, `row_counts.parent_relation` must equal three times `row_counts.pedigree_fact`: one sire, dam, and broodmare-sire row per child. The common `tools/data-storage/` converter validates row counts and canonical key uniqueness before the manifest is written. The audit records source counts, coverage, relation statuses for the full master and 2025 cohort, recursive diagnostics, lineage frequencies and unmapped codes, and alias evidence counts.

Consumers must verify the manifest fields, file hashes, row counts, canonical keys, and required files before using a generation. Production publication and reader contracts are separate future work; the existence of this generation does not change the operational `CURRENT`.

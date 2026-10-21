# BRDB Pedigree Fact Schema v0.1

Status: IMPLEMENTED BASELINE  
Date: 2026-10-21

## Scope

BRDB v0.1 separates four concerns:

1. immutable/current pedigree fact
2. parent relation resolution
3. explicit pedigree-name aliases
4. lineage-code master

Blood Review scoring is intentionally outside this schema.

## Canonical tables

### pedigree_fact

One current canonical profile per `horse_id`.

Primary source: JRDB UKC.

Core fields:

- horse_id
- horse_name
- birth_date
- sex_code
- sire_name / sire_birth_year
- dam_name / dam_birth_year
- broodmare_sire_name / broodmare_sire_birth_year
- sire_line_code
- broodmare_sire_line_code
- breeding_place
- profile_data_date
- semantic_hash
- source_family
- source_generation

### parent_relation

Stores relation-resolution result separately from pedigree fact.

Roles:

- sire
- dam
- broodmare_sire

A relation may remain unresolved.

Statuses:

- RESOLVED_EXACT
- RESOLVED_ALIAS
- NO_CANDIDATE
- MULTIPLE_CANDIDATES
- INSUFFICIENT_KEY
- INSUFFICIENT_GUARD
- CONFLICT

The existence of a unique `parent_name + parent_birth_year` candidate is not sufficient to create a canonical relation.

### pedigree_name_alias

Explicit versioned aliases only.

No fuzzy matching is allowed at runtime.

Alias evidence must retain:

- birth_year
- lineage_code
- evidence_type
- evidence_count
- observed period
- alias_version
- source_generation

### lineage_code_master

JRDB official lineage code mapping.

Fields:

- lineage_code
- major_code
- major_name
- minor_name
- source_name
- source_version

The first official source confirmed for this project is JRDB `code__keito`, dated 2003-05-15.

## Relation resolver contract

Implementation:

`horse-racing/brdb/src/brdb_parent_relation.py`

### Candidate generation

Candidate lookup begins from:

`parent_name + parent_birth_year`

Expected sex is also enforced:

- sire: male
- dam: female
- broodmare sire: male

Approved aliases may expand the exact candidate name set.

### Sire / broodmare-sire guard

A unique candidate is accepted only when candidate paternal lineage equals the child's independently supplied corresponding lineage code.

Missing lineage evidence is fail-closed as `INSUFFICIENT_GUARD`.

### Dam guard

A unique dam candidate is accepted only when all independent BMS evidence agrees:

- candidate sire birth year == child broodmare-sire birth year
- candidate sire lineage == child broodmare-sire lineage
- candidate sire name == child broodmare-sire name
  OR an approved explicit alias establishes equivalence

The Vivalda collision found in the 2025 audit must remain a regression case.

## Validation

Focused synthetic resolver tests:

- exact sire/dam/BMS resolution
- real-pattern false dam collision fails closed
- approved spelling alias resolves
- duplicate exact candidates remain unresolved
- lineage conflict remains unresolved
- missing guard remains unresolved
- missing candidate remains unresolved

Result: 7/7 PASS.

The SQL schema was also executed against in-memory SQLite and all five tables were created successfully.

## Next implementation

1. populate lineage_code_master from official JRDB code table;
2. freeze reviewed alias v0.1 from the audited spelling variants;
3. build UKC -> pedigree_fact generation builder using existing `jrdb_ukc.py`;
4. generate parent_relation with the guarded resolver;
5. run full 2010-2025/2026 coverage and conflict audit;
6. publish immutable BRDB pedigree generation before adding Review scoring.

# BRDB Existing Pedigree Asset Inventory v0.1

Status: ACTIVE INVENTORY BASELINE
Date: 2026-10-21

## Confirmed reusable assets

### Canonical identity
BRDB canonical horse identity:
- horse_id = JRDB blood_registration_no
- horse-name fallback prohibited

### JRDB UKC
Current parser: horse-racing/jrdb/src/jrdb_ukc.py

Available fields:
- horse_id
- horse_name
- sex_code
- coat_color_code
- horse_symbol_code
- sire_name
- dam_name
- broodmare_sire_name
- birth_date
- sire_birth_year
- dam_birth_year
- broodmare_sire_birth_year
- owner_name
- breeder_name
- breeding_place
- deregistered_flag
- data_date
- sire_line_code
- broodmare_sire_line_code

Historical UKC Warehouse objects are indexed for 2010-2025.
2026 daily UKC availability has already been verified as pre-race usable under:
docs/Debut_Ability_UKC_Availability_Decision_20260903.md

Accepted profile chronology:
latest UKC observation where data_date <= target race date.

### RaceNote pedigree
Reference:
docs/racenote/RACENOTE_PEDIGREE_ENRICHMENT_DESIGN_v0_1.md

P1 implemented:
- sire_name
- dam_name
- broodmare_sire_name
- sire_line_code
- broodmare_sire_line_code
- coverage/provenance

Current normal Analysis-backed path usually has dam_name=null because Analysis v1.4 does not carry dam_name.

P2 implemented:
- sire x venue x surface x exact distance
- sire x venue x surface x distance range
- broodmare sire x venue x surface x exact distance
- broodmare sire x venue x surface x distance range
- starts/wins/top3/rates/sample-size/as-of provenance

### Analysis canonical
Current v1.4 pedigree fields:
- horse_id
- horse_name
- sire_name
- broodmare_sire_name
- sire_line_code
- broodmare_sire_line_code

Analysis should remain historical performance input, not the BRDB pedigree master.

### Edge Feature Mart
Current feature mart already resolves the latest horse profile observation as-of race date and carries:
- birth_date
- sire_name
- sire_line_code
- broodmare_sire_name
- broodmare_sire_line_code

This chronology pattern is reusable.

### Existing PEDIGREE_CROSS research
EdgeDB v0.4 already evaluated a PEDIGREE_CROSS family over five years.
Decision: PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY
Production impact: NONE

This is research reference only and must not be imported as BRDB scoring logic.

## Confirmed gaps

1. Stable sire/dam/broodmare-sire horse IDs are not confirmed.
2. Canonical 3-5 generation ancestor graph is not confirmed.
3. Canonical mapping from JRDB line codes to reader labels is not yet confirmed.
4. Japanese/US/European regional-type taxonomy does not yet exist.
5. Speed/stamina/power/sustain etc. type taxonomy does not yet exist.
6. Canonical per-horse cross/inbreeding structure does not yet exist.
7. Pedigree similarity engine does not exist.
8. Stable maternal identity for canonical sibling relation is not yet confirmed.

## BRDB pedigree fact v0.1 candidate

The first canonical table can be built from UKC only:

- horse_id
- horse_name
- birth_date
- sex_code
- sire_name
- sire_birth_year
- dam_name
- dam_birth_year
- broodmare_sire_name
- broodmare_sire_birth_year
- sire_line_code
- broodmare_sire_line_code
- breeding_place
- profile_data_date
- semantic_hash
- source_family
- source_generation

This is enough to begin BRDB without waiting for an external 3-5 generation pedigree source.

## Next checks

1. Inspect official JRDB definitions for sire_line_code / broodmare_sire_line_code.
2. Confirm whether another JRDB family exposes parent IDs or deeper pedigree.
3. Freeze BRDB_PEDIGREE_FACT_SCHEMA_v0_1.
4. Run UKC coverage audit over representative 2010-2026 data.
5. Decide external source requirements only for information JRDB truly lacks.

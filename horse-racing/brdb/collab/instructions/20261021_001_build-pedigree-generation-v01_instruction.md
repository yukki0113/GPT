# BRDB Codex Instruction 20261021-001 — Build Pedigree Canonical Generation v0.1

Status: READY  
Date: 2026-10-21  
Project: `horse-racing/brdb`

## Objective

Implement and execute BRDB Pedigree Canonical Generation v0.1 from JRDB UKC.

This task begins after the following design decisions are already fixed on `main`:

- BRDB canonical identity = JRDB blood registration number `horse_id`
- horse-name fallback is prohibited
- `parent_name + parent_birth_year` is a candidate key only
- parent relation resolution must fail closed on independent pedigree conflicts
- runtime fuzzy matching is prohibited
- aliases must be explicit/versioned
- JRDB official lineage code table is canonical for sire/BMS lineage labels
- durable analytical storage is immutable Parquet using repository common `tools/data-storage/`
- PWA/RaceNote must not read internal Parquet directly

Do not redesign these contracts.

## Mandatory preflight

Read in this order:

1. `.gpt/GITHUB_OPERATION_POLICY.md`
2. `tools/codex-cloud/README.md`
3. `horse-racing/brdb/README.md`
4. `horse-racing/brdb/.gpt/CONTEXT.md`
5. `horse-racing/brdb/.gpt/WORKFLOW.md`
6. `horse-racing/brdb/docs/BRDB_EXISTING_PEDIGREE_ASSET_INVENTORY_v0_1.md`
7. `horse-racing/brdb/docs/BRDB_PEDIGREE_FACT_SCHEMA_v0_1.md`
8. `horse-racing/brdb/docs/BRDB_UKC_PARENT_KEY_JOIN_VALIDATION_20261021.md`
9. `horse-racing/brdb/docs/BRDB_UKC_DAM_BMS_INCONSISTENCY_AUDIT_20261021.md`
10. `horse-racing/brdb/schema/brdb_pedigree_fact_schema_v0_1.sql`
11. `horse-racing/brdb/src/brdb_parent_relation.py`
12. `horse-racing/brdb/tests/test_brdb_parent_relation.py`
13. `horse-racing/brdb/config/lineage_code_master_v0_1.csv`
14. `horse-racing/jrdb/src/jrdb_ukc.py`
15. `tools/data-storage/README.md`

Before editing, use the built-in GitHub connector to inspect relevant open PRs/pending branches for BRDB.

## Canonical input

Primary historical Raw source is Google Drive UKC annual archives:

`UKC_2010.zip` through `UKC_2025.zip`

Known folder:

`https://drive.google.com/drive/folders/14fcCC82yn3sRE7X3OY75m4hvrKTqVt5a`

Use the connected Google Drive connector. Do not use service accounts, legacy adapters, or ad-hoc Web scraping.

Known audit baseline from ChatGPT:

- 780,855 valid UKC observations across 2010-2025
- 0 invalid 290-byte UKC record bodies
- 82,107 unique horses after latest-observation reduction
- 11,818 horses appearing in 2025 UKC

These values are audit expectations, not values to hardcode. Recompute them.

If an approved 2026 daily UKC source can be resolved from the connected Drive/repository without guessing, include it as an additional source generation. Do not block the v0.1 historical build if only 2010-2025 is reproducibly available.

## Existing parser reuse

Use:

`horse-racing/jrdb/src/jrdb_ukc.py`

Do not reimplement the fixed-width offsets.

If a clean package import boundary is needed, add only the minimum reusable wrapper needed. Do not copy field parsing into BRDB.

## Required implementation

### 1. Generation builder

Add a BRDB-owned deterministic builder, recommended path:

`horse-racing/brdb/src/build_brdb_pedigree_generation.py`

Responsibilities:

1. accept one or more UKC ZIP paths/directories;
2. extract/read all `UKC*.txt` records through existing `jrdb_ukc.parse_ukc_record`;
3. validate record length;
4. reduce observations to the latest profile per `horse_id`;
5. produce canonical `pedigree_fact`;
6. load official `lineage_code_master_v0_1.csv`;
7. load an explicit alias master if present;
8. build `parent_relation` using `brdb_parent_relation.py`;
9. write staging SQLite or deterministic CSV relations as appropriate;
10. use repository common `tools/data-storage/` for Parquet creation/validation;
11. create immutable generation output;
12. write a manifest and machine-readable audit.

Do not create a persistent DuckDB database.

### 2. Source chronology

Latest-profile rule:

```text
latest UKC observation per horse_id by data_date
```

If duplicate observations exist at the same max `data_date`:

- identical semantic_hash -> collapse deterministically;
- differing semantic_hash -> fail validation and report the horse_id.

Do not silently choose one.

### 3. Pedigree fact

Populate the fields fixed by:

`schema/brdb_pedigree_fact_schema_v0_1.sql`

At minimum:

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

### 4. Lineage master

Materialize:

`horse-racing/brdb/config/lineage_code_master_v0_1.csv`

into the generation.

Validate:

- lineage_code unique
- major_code = first two digits of lineage_code
- no empty major/minor name
- all non-empty UKC sire_line_code / broodmare_sire_line_code values are either mapped or explicitly reported as unmapped

Do not invent mappings for unknown codes.

### 5. Alias v0.1

Recompute the dam/BMS apparent inconsistency audit from the full canonical source.

Use the existing audit document as the expected pattern, not as a hardcoded final result.

Build a reviewed candidate artifact, recommended:

`horse-racing/brdb/config/pedigree_name_alias_v0_1.csv`

Only promote aliases that meet deterministic evidence.

Minimum accepted evidence:

- same birth year
- same lineage code
- repeated UKC relation evidence and/or historical spelling revision evidence

Required fields:

- observed_name
- canonical_name
- birth_year
- lineage_code
- evidence_type
- evidence_count
- first_observed
- last_observed
- alias_version
- source_generation

Do not use Levenshtein/fuzzy similarity as acceptance evidence.

Expected previously observed pattern:

- 101 apparent dam/BMS inconsistencies on 2025 target cohort
- 100 spelling/transliteration cases
- 1 genuine collision involving `ヴィヴァルダ + 2015`

Recompute; if numbers differ, explain why.

### 6. Parent relation

Use the existing guarded resolver.

For each child horse, independently produce relation rows for:

- sire
- dam
- broodmare_sire

Expected statuses:

- RESOLVED_EXACT
- RESOLVED_ALIAS
- NO_CANDIDATE
- MULTIPLE_CANDIDATES
- INSUFFICIENT_KEY
- INSUFFICIENT_GUARD
- CONFLICT

Do not coerce unresolved cases into resolved IDs.

The known Vivalda collision must remain unresolved/CONFLICT.

### 7. Parquet generation

Use `tools/data-storage/`.

Recommended immutable layout:

```text
brdb-pedigree-generation-<generation_id>/
  current.json              # only if implementing local generation pointer fixture
  manifest.json
  pedigree_fact.parquet
  parent_relation.parquet
  pedigree_name_alias.parquet
  lineage_code_master.parquet
  audit.json
```

Do not publish/replace a production CURRENT pointer in this task unless an existing BRDB publication contract already exists and explicitly permits it.

This task is foundation validation, not production serving cutover.

### 8. Manifest

Manifest must record at least:

- artifact_type = brdb_pedigree
- generation_id
- schema_version
- builder_version
- source family
- source archive count
- source date range
- source identities / hashes where available
- row counts per relation
- canonical key definitions
- alias version
- lineage source version
- validation_status
- output SHA-256 values

## Full-data audit requirements

Run against all reproducible 2010-2025 UKC archives.

Report:

### Source
- archive count
- text member count
- raw observation count
- invalid record count
- min/max data_date
- unique horse_id count

### Pedigree field coverage
For canonical horses:
- sire name/year coverage
- dam name/year coverage
- BMS name/year coverage
- sire lineage coverage
- BMS lineage coverage

### Relation resolution
For sire/dam/BMS separately:
- RESOLVED_EXACT
- RESOLVED_ALIAS
- NO_CANDIDATE
- MULTIPLE_CANDIDATES
- INSUFFICIENT_KEY
- INSUFFICIENT_GUARD
- CONFLICT
- resolution percentage

Also report the same for the 2025 target cohort to compare with the existing audit.

### Recursive diagnostic only
Measure how many targets can resolve:
- sire's sire
- sire's dam
- dam's sire
- dam's dam

This is diagnostic only. Do not expand BRDB v0.1 schema into a 3-5 generation graph in this task.

### Lineage
- all observed lineage codes
- mapped count
- unmapped values
- major/minor frequency

### Alias
- candidate pair count
- promoted alias pair count
- affected relation rows
- historical-spelling-evidence count
- repeated-relation-evidence count

## Tests

Keep existing tests passing.

Add focused tests for the builder covering:

1. latest observation wins;
2. identical same-date duplicate collapses;
3. conflicting same-date duplicate fails;
4. bad UKC record length fails;
5. lineage master loads and validates;
6. unknown lineage code is reported/fails according to documented policy;
7. exact parent relation;
8. approved alias relation;
9. Vivalda-pattern false collision fails closed;
10. generation manifest row counts/hashes are stable;
11. repeated run on same inputs produces identical semantic outputs apart from generated timestamps.

Use small fixtures for unit tests. Do not require 16-year Drive data in normal unit tests.

## Result document

Create:

`horse-racing/brdb/collab/results/20261021_001_build-pedigree-generation-v01_result.md`

Include:

- Status: DONE / BLOCKED
- exact source inputs
- source commit
- implementation files changed
- commands run
- Python/DuckDB/PyArrow versions
- full-data audit results
- previous baseline comparison
- alias findings
- lineage findings
- relation status distribution
- Parquet row counts and hashes
- test results
- output Drive/artifact location if large outputs are persisted
- branch
- commit SHA
- PR number
- pending merge state
- unresolved items
- recommended next action

Do not put large Parquet outputs into Git.

## Acceptance criteria

PASS only if all are true:

1. existing `jrdb_ukc.py` parser is reused;
2. all 2010-2025 archives are processed;
3. canonical horse reduction is deterministic;
4. pedigree_fact has unique non-empty horse_id;
5. official lineage master is loaded and audited;
6. parent relation uses guarded resolver and fails closed;
7. Vivalda collision does not resolve incorrectly;
8. no runtime fuzzy matching is introduced;
9. aliases are explicit/versioned/evidence-backed;
10. Parquet is built through repository common data-storage utilities;
11. immutable manifest/audit exist;
12. focused tests pass;
13. full-data audit is recorded;
14. no production CURRENT/PWA cutover occurs.

## Non-goals

- no Blood Review score
- no JP/US/EU regional taxonomy
- no 3-5 generation canonical graph
- no similar-pedigree engine
- no PWA changes
- no RRDB changes
- no production CURRENT pointer cutover

## Codex Cloud execution rules

- Use the published GPT Cloud Environment.
- Treat this instruction file and repository docs as canonical.
- Before concluding that a file or prerequisite is missing, inspect relevant open PRs / pending branches with the built-in GitHub connector.
- Record relevant pending-merge PRs/branches in the requested RESULT.
- Do not depend on shell git fetch/pull/push.
- For GitHub writes, use the built-in GitHub connector.
- Create a working branch and PR; do not write directly to main.
- Use the connected Google Drive connector for normal Drive access.
- Do not fall back to legacy Drive API adapters, service accounts, or gdown unless explicitly authorized.
- Keep large source/intermediate datasets out of Git.
- Preserve reproducible commands, tests, audit results, and unresolved issues in the requested RESULT Markdown.
- If an approval reviewer fails because of model capacity, do not repeatedly retry shell Git writes; preserve completed work and switch GitHub reflection to the built-in connector.

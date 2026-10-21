# BRDB UKC Parent-Key Join Validation 2026-10-21

Status: PASS WITH COVERAGE LIMITATION

## Objective

Validate whether JRDB UKC parent fields can be used to reconstruct pedigree links by exact:

- parent name
- parent birth year

without external Web data.

## Source

Canonical Drive Raw UKC annual archives:

- UKC_2010.zip through UKC_2025.zip
- 16 annual archives
- existing JRDB UKC fixed-width specification
- exact 290-byte body records

The official UKC specification labels sire/dam/broodmare-sire birth year as pedigree-key fields.

## Method

1. Read every UKC record from 2010-2025.
2. Keep the latest observation per horse_id.
3. Build a master index by exact:
   `(horse_name, birth_year)`
4. Use sex only as a consistency discriminator:
   - sire / broodmare sire: male
   - dam: female
5. No fuzzy name matching.
6. No Web supplementation.
7. Target cohort: every unique horse appearing in UKC_2025.

## Input scale

- raw UKC observations: 780,855
- invalid record length: 0
- unique horses in 2010-2025 latest-observation master: 82,107
- 2025 target horses: 11,818

## First-generation link result

| Role | Unique match | No match | Ambiguous | Match rate |
|---|---:|---:|---:|---:|
| sire | 7,739 | 4,079 | 0 | 65.48% |
| dam | 8,198 | 3,620 | 0 | 69.37% |
| broodmare sire | 1,064 | 10,754 | 0 | 9.00% |

All 11,818 target records had parent name + parent birth year populated for all three roles.

No exact name+birth-year ambiguity was observed in this cohort.

## Main race-age cohort

For horses born 2022-2023 (7,755 horses):

| Role | Match rate |
|---|---:|
| sire | 67.84% |
| dam | 72.16% |
| broodmare sire | 11.58% |

For horses born 2021-2023 (9,462 horses):

| Role | Match rate |
|---|---:|
| sire | 66.53% |
| dam | 71.42% |
| broodmare sire | 10.61% |

The basic result is therefore not caused by old inactive target horses in the 2025 file.

## Parent-level coverage

At least one of sire/dam resolved for:

- 10,479 / 11,818 = 88.67%

Both sire and dam resolved for:

- 5,458 / 11,818 = 46.18%

This makes exact first-generation parent linking useful as an enrichment path.

## Grandparent recursion

Grandparent nodes resolvable through matched sire/dam records:

| Grandparent node | Unique match | Rate over all targets |
|---|---:|---:|
| sire's sire | 319 | 2.70% |
| sire's dam | 604 | 5.11% |
| dam's sire | 946 | 8.00% |
| dam's dam | 1,180 | 9.98% |

Conditional on the direct parent itself resolving:

| Grandparent node | Conditional rate |
|---|---:|
| sire's sire | 4.12% |
| sire's dam | 7.80% |
| dam's sire | 11.54% |
| dam's dam | 14.39% |

Number of resolved grandparent records per target:

- 0: 9,271
- 1: 2,070
- 2: 452
- 3: 25
- 4: 0

No target horse had all four grandparents recursively resolved from the 2010-2025 UKC horse master.

Therefore UKC-only recursive self-join is not sufficient for a canonical complete 3-generation pedigree tree.

## Dam / broodmare-sire consistency check

Where dam resolved uniquely:

- dam resolved: 8,198
- target BMS key equals resolved dam's sire key: 8,096
- inconsistent: 101

Consistency rate:

- 98.77%

This strongly supports parent name + birth year as a meaningful exact pedigree key when the parent horse exists in the UKC master.

The 101 apparent inconsistencies were audited separately in `BRDB_UKC_DAM_BMS_INCONSISTENCY_AUDIT_20261021.md`. Of these, 100 are spelling/transliteration variants and 1 is a genuine false collision for exact name + birth year. Therefore name + birth year is accepted only as a candidate resolver, not as an unconditional canonical relation key.

## Unresolved-key pattern

Frequent unmatched sires include:

- Drefong (2013)
- Bricks and Mortar (2014)
- Harbinger (2006)
- Sinister Minister (2003)
- Henny Hughes (2003)
- Declaration of War (2009)

Frequent unmatched broodmare sires include:

- Deep Impact (2002)
- King Kamehameha (2001)
- Kurofune (1998)
- Heart's Cry (2001)
- Daiwa Major (2001)
- Symboli Kris S (1999)

This pattern is consistent with a coverage-window limitation and horses whose own JRDB UKC observation is not present in the 2010-2025 master. It is not an ambiguity problem in exact name+birth-year matching.

## Decision

### Accepted

BRDB may use exact:

`parent_name + parent_birth_year`

as an optional relation-resolution key against the UKC horse master.

When exactly one horse resolves, BRDB may attach that parent horse_id with provenance:

`relation_resolution = UKC_EXACT_NAME_BIRTH_YEAR`

### Not accepted

Do not use the UKC 2010-2025 self-join as the sole source for complete 3-5 generation pedigrees.

Do not fuzzy-match unresolved parents.

Do not treat no-match as missing parent identity; it means only that the parent's own horse record is outside current UKC master coverage.

### Architecture consequence

BRDB v0.1 can safely support:

- sire/dam/BMS names and birth years for all observed target horses
- official sire-line and BMS-line codes
- optional resolved sire horse_id (~65-68%)
- optional resolved dam horse_id (~69-72%)
- parent relation provenance
- first-generation display and review

Complete 3-5 generation pedigree expansion still needs an additional canonical pedigree source or a broader historical horse master.

## Follow-up

1. Audit the 102 dam/BMS key inconsistencies.
2. Check whether older JRDB UKC archives before 2010 exist and materially improve recursive coverage.
3. If not, evaluate an external pedigree master only for unresolved ancestors.
4. Keep JRDB facts primary and external data supplementary.

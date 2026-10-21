# BRDB Pedigree Canonical Generation v0.1 — Result

Status: DONE (implementation, full-data validation, and immutable Drive persistence verified; optional alias CSV publication to GitHub is not required for canonical generation)  
Date: 2026-10-21  
Source commit: `5cdeed75a95b1efc24c5fcab551befcc35ddb54c`  
Branch: `codex/brdb-pedigree-generation-v01-20261021`  
Implementation commit: `fe511d4f9ea53b0802845b29f11be140259d56b3`  
PR: #2126 (draft; pending merge)

## Execution

Inputs: the 16 UKC annual archives `UKC_2010.zip` through `UKC_2025.zip`, obtained with the connected Google Drive connector. The builder reused `jrdb_ukc.parse_ukc_record`, the guarded BRDB resolver, and common `tools/data-storage/` Parquet conversion and validation. No reproducible approved 2026 daily archive was found.

Python 3.12.14; DuckDB 1.1.3; PyArrow 25.0.1. Commands:

```bash
PYTHONPATH=<installed-data-storage-dependencies> python horse-racing/brdb/src/build_brdb_pedigree_generation.py <UKC-archive-directory> --output-root <temporary-output-directory>
PYTHONPATH=<installed-data-storage-dependencies> python -m unittest discover -s horse-racing/brdb/tests -q
```

Tests: 13 passed. No production CURRENT pointer or consumer was changed.

## Full-data audit

| Metric | Recomputed | Prior baseline |
|---|---:|---:|
| archives | 16 | 16 |
| text members | 1,732 | — |
| observations | 780,855 | 780,855 |
| invalid record bodies | 0 | 0 |
| data-date range | 2010-01-05 to 2025-12-28 | — |
| canonical horses | 82,107 | 82,107 |
| 2025 target horses | 11,818 | 11,818 |

Canonical field coverage (name and birth year present): sire 82,107; dam 82,106; broodmare sire 82,107. Sire lineage coverage: 82,100; broodmare-sire lineage coverage: 82,103.

Relation statuses are exact / alias / no candidate / multiple candidates / insufficient key / insufficient guard / conflict.

| Cohort | Role | Status counts | Resolved |
|---|---|---|---:|
| all | sire | 24,277 / 0 / 57,829 / 0 / 0 / 0 / 1 | 29.5675% |
| all | dam | 26,360 / 328 / 55,376 / 0 / 1 / 0 / 42 | 32.5039% |
| all | broodmare sire | 1,555 / 0 / 80,550 / 0 / 0 / 0 / 2 | 1.8939% |
| 2025 | sire | 7,731 / 0 / 4,087 / 0 / 0 / 0 / 0 | 65.4172% |
| 2025 | dam | 8,089 / 99 / 3,623 / 0 / 0 / 0 / 7 | 69.2841% |
| 2025 | broodmare sire | 1,053 / 0 / 10,763 / 0 / 0 / 0 / 2 | 8.9101% |

The prior 2025 audit measured candidate-only matches: sire 7,739; dam 8,198; broodmare sire 1,064. Guarded, sex-constrained resolution yields fewer accepted relations. Recursive diagnostic for 2025 targets: sire's sire 319; sire's dam 604; dam's sire 943; dam's dam 1,179.

The apparent dam/BMS mismatch pattern reproduced: 101 cases, 100 spelling cases, one genuine collision. The collision remains unresolved. There were 22 candidate alias pairs; 21 met repeated relation and/or historical spelling evidence, while one did not. Historical spelling evidence affected 23 observations; repeated relation evidence affected 96. Versioned aliases affected 328 resolved dam relations in the full master.

Official JRDB lineage master: 83 rows; 62 distinct codes observed; no unmapped observed codes. Full code and major/minor frequencies remain in the generated audit.

## Generation and publication state

Generation ID: `eeca93556584a5b8`. Validated Parquet rows: pedigree fact 82,107; parent relation 246,321; aliases 21; lineage master 83. The local immutable generation includes a manifest, source and output SHA-256 values, and a machine-readable audit. Large Parquet files were kept out of Git.

The alias master CSV was generated locally with explicit version and evidence fields. Automatic approval review rejected publishing that individual-level CSV to GitHub as outside the authorized code-and-aggregate scope. An earlier attempt to upload the ZIP to a newly created Drive folder was rejected because destination ownership, trust, and specific authorization were not established. The user subsequently supplied an explicit Drive destination. Four Parquet files, `manifest.json`, and `audit.json` were uploaded to a generation subfolder there and verified by folder readback. The previously created folder remains empty. An earlier detailed RESULT containing individual-level data and private source metadata was also rejected; no rejected transfer was bypassed.

Code and contract changes: generation builder, resolver correction, focused tests, manifest JSON Schema, manifest contract documentation, and BRDB README index. The pedigree fact SQL schema was already on main. The resolver correction prevents an unused alias from relabeling an exact match. Related open BRDB PRs/branches at preflight: none.

The immutable Parquet generation is externally persisted in the user-designated Drive folder and its files were verified against the generation manifest. Publishing a separate reviewed alias CSV to GitHub is optional and is not a blocker for the canonical generation. Recommended next action: merge this implementation PR and proceed to the BRDB CURRENT / Reader publication design.

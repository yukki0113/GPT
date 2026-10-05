# JRDB Feature Audit Stage B — Artifact Ingest Manifest

Date: 2026-10-05  
Source: user-supplied `20261005_JRDB_FEATURE_AUDIT_STAGE_B_ARTIFACTS.zip`  
Bundle SHA-256: `fabe407d06e31bd90f3d73a9068541581c961066abc8da4c5f246e39375ba0d1`

## Canonical interpretation

The supplied bundle was inspected before acceptance. Its Stage B report and
machine outputs are represented by the Stage B audit and this checksum
manifest. The machine tables are deterministic derivatives of the supplied
pipeline and frozen annual raw inputs.

Primary cohort:

- window: 2023-01-01 through 2025-12-31
- races: 10,365
- runner entries: 142,737
- valid-result entries: 141,523
- scalar feature leaves: 73
- recommendation: PROCEED_STAGE_C

## Supplied artifact checksums

| Path inside supplied bundle | Size bytes | SHA-256 |
|---|---:|---|
| `.gitignore` | 662 | `e0cc1bdf107a67f3f0323b8e66c1ed1e82e7d715e0c0e9f0331802262404061a` |
| `horse-racing/jrdb/tools/run_racenote_feature_audit_stage_b.py` | 37,364 | `a946409b58a5c022c90b6bec2b9b04d156b444825d5fc8c590209896d43f0364` |
| `reports/20261005_JRDB_FEATURE_AUDIT_STAGE_B_REPORT.md` | 14,387 | `0ea8987f52047a52525c373e431263ff2d812b39f099b2692c7ff9c2bbaa8067` |
| `results/stage_b_2023_2025/cohort.json` | 231 | `0350f5091ae2a3ac212f59c17c3c6a3304d0f64c0d23b977c8630fc0e6be3960` |
| `results/stage_b_2023_2025/outcome_quality.json` | 329 | `a61bc9f621b6ac45bbd6c20efd40d0970f9eceb136ec8ffe848a3b5ced91d088` |
| `results/stage_b_2023_2025/source_coverage.json` | 2,627 | `a55385697eef21408810c0dfa8ea6b59c7b9ac4962e11df2c7823114920bdd62` |
| `results/stage_b_2023_2025/source_manifest.json` | 3,641 | `a122282167bd0f2fa249116abba62b60aa8950e4f4e413dc6ed3c1c49c75e52f` |
| `results/stage_b_2023_2025/scalar_feature_catalog.json` | 28,759 | `c3ca873fe8757cbc08f4ef87ab7b86b8fbb30d936535c4cb382ea47d1d0a5d56` |
| `results/stage_b_2023_2025/coverage.csv.gz` | 2,861 | `de6596a105b8bc5652ce2349b196d0c53331d37598088426f0852f04b5bb8da8` |
| `results/stage_b_2023_2025/raw_distributions.csv.gz` | 2,170 | `029182dc1e44c766e8ef4b42c304ef2906ed739c7a2c5b2fe038cefe47807c26` |
| `results/stage_b_2023_2025/numeric_transform_summary.csv.gz` | 4,515 | `f0ee665527f6cc3f1d6865834274011caef2cdc748724668a7997bb1ba95b52c` |
| `results/stage_b_2023_2025/overall_metrics.csv.gz` | 30,329 | `753c18c0c31d7c6fcc3f099fc61c0b9b3c04d284a74dd9f481fbb1ccdb881f3e` |
| `results/stage_b_2023_2025/yearly_metrics.csv.gz` | 84,987 | `409fbde93317ce830d6391542482ed3d6c7b67102bf9a0ae751d13bbdccf9479` |
| `results/stage_b_2023_2025/monotonicity.csv.gz` | 6,092 | `403841d15f929a2b9d9a68ddc6506352036e7ad9e0d42b81ab6f74a3e69f3bb0` |
| `results/stage_b_2023_2025/market_strata.csv.gz` | 134,222 | `86a5f62320512b2cb4b04fcb9935cdcf4947252866fd01ecc38460607476d024` |
| `results/stage_b_2023_2025/provider_rank_comparison.csv.gz` | 404 | `2a60caf1576f02df9667668b0eea26fda6f4be3d360132b22e3d48ac6042586b` |
| `results/stage_b_2023_2025/redundancy_pairs.csv.gz` | 9,925 | `d0ea347bb560b44aacfde1abf30e5725028a47b983f951abb5e7a9df3b163ebb` |
| `results/stage_b_2023_2025/mark_index_overlap.csv.gz` | 1,010 | `0eebef0380966a127faf8c7700eb5a50ce3ca8ab59b1ee069f33c5549ccbbb81` |
| `results/stage_b_2023_2025/conditional_slices.csv.gz` | 56,822 | `8b2e23f46be3b2d3cb2ade5bcbdd9471576dda48d744353c5106f6105c46292f` |

The supplied pipeline reported byte-identical deterministic regeneration of
its result set with aggregate result hash
`ed209ff20b8a2266a661f86687a69dee6c39f755e5cdfaab479a774fad406201`.

## Audit status

Accepted by:
`audits/20261005_JRDB_FEATURE_AUDIT_STAGE_B_AUDIT.md`

Next:
`instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_C_INSTRUCTION.md`

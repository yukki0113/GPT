# Blood Review v0.1 verification result

Status: **PASS — contract frozen; PR review pending**  
Date: 2026-10-22  
Source main commit: `a0388ce3e1d1c405b3b1b598b5bfa1ba17db3da3`

## Environment and tests

Python 3.12.14, DuckDB 1.1.3, PyArrow 25.0.1.

```bash
PYTHONPATH=/workspace/scratch/brdb-pylibs python -m unittest discover -s horse-racing/brdb/tests -q
```

Result: **38 tests PASS, 0 FAIL, 0 ERROR**. The suite includes as-of/profile guard, wrong producer/source/identity/scope, duplicate IDs, zero starts, output result filtering and batch/single equivalence cases.

## Real authoritative field replay

Input: `horse-racing/jrdb/backtests/BTDAY-0125/20251026/day_prep/RaceNote_20251026/authoritative/race_bundle_20251026_京都1R.json` (GitHub blob `df541481742a28b16e19513cf45c56a7150f4e0b`). Race: 2025-10-26 京都1R, ダート1800m. This is a real enriched authoritative RaceNote bundle, not a synthetic fixture.

BRDB CURRENT: `config/public_drive/brdb_current_v0_1.json`; pinned ZIP SHA-256 `c0eda6fc55472a4a7a327dcbee6498063bf19209285dfa0b4bc0284ba554305f`; verified generation `eeca93556584a5b8`. The resolver validated transport size/SHA and Reader validated generation manifest and object hashes. DuckDB read the pedigree Parquet.

Exact replay invocation (bundle and ZIP paths are local copies of the refs above):

```bash
PYTHONPATH=/workspace/scratch/brdb-pylibs python horse-racing/brdb/src/run_brdb_blood_review_field_replay.py \
  --race-bundle /workspace/scratch/brdb_verify_real_bundle_20251026_kyoto1.json \
  --current-zip /workspace/attachments/669580f7-33c3-4162-83e2-727396590266/BloodReviewDB_CURRENT.zip \
  --cache-root /workspace/scratch/brdb-current-verify \
  --source-commit a0388ce3e1d1c405b3b1b598b5bfa1ba17db3da3 \
  --input-ref horse-racing/jrdb/backtests/BTDAY-0125/20251026/day_prep/RaceNote_20251026/authoritative/race_bundle_20251026_京都1R.json \
  --output /workspace/scratch/brdb_field_replay_20251026_kyoto1_aggregate.json
```

| Aggregate | Count |
| --- | ---: |
| Requested / produced | 9 / 9 |
| P2 producer adapted sire / BMS roles | 9 / 9 |
| AVAILABLE | 5 |
| AS_OF_UNVERIFIED | 4 |
| P2 FULL / PARTIAL / NONE after as-of guard | 5 / 0 / 4 |
| Identity withheld: profile not date-safe | 4 |
| Fail closed | 4 |
| Batch/single mismatches across all target IDs | 0 |
| Scores / regional type produced | 0 / 0 |

The four AS_OF_UNVERIFIED records have pedigree facts and P2 withheld. No target result fields are in review output. No per-horse output is included in this report.

Real-bundle negative probes: changed as-of, horse_id, venue, distance and missing producer provenance were each rejected by the adapter (**5 PASS, 0 FAIL**). Producer P2 accepts zero starts as a valid factual count.

## Scope

Review v0.1 remains descriptive. The contract and status fields are frozen in `docs/BRDB_REVIEW_CONTRACT_v0_1.md`. This task did not rebuild UKC, modify the immutable generation, or change RRDB/RaceNote/PWA production. The PR is left unmerged for review.

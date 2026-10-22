# BRDB Blood Review v0.1

Status: **VALIDATED / CONTRACT FROZEN**  
Date: 2026-10-22

Blood Review v0.1 returns descriptive evidence for every requested horse. It does not assign suitability, a score, regional type, positive or negative factors. The frozen fields and statuses are in `BRDB_REVIEW_CONTRACT_v0_1.md`.

## Source and safety

`src/brdb_blood_review.py` queries pedigree facts only through `BloodReviewReader.horse_pedigree(horse_id)`. The Reader validates the pinned immutable CURRENT and uses DuckDB. No horse-name fallback is allowed. A profile whose `profile_data_date` is missing or later than the target is `AS_OF_UNVERIFIED`; its facts and P2 are withheld.

`src/brdb_racenote_p2_adapter.py` reads an existing authoritative RaceNote bundle. It verifies `race`, `metadata.history_enrichment`, nested `pedigree_enrichment` (P1-0.1/P2-0.1), as-of-exclusive leakage policy, condition scope, descriptive-only flags, exact complete cohort and unique canonical `horses[].basic.horse_id`. Per-horse `pedigree.horse_id` and source policy must agree. Each role's source, as-of, count bounds, sample band, period and distance ranges are checked. The engine then compares sire/BMS names against canonical Reader facts. Invalid roles are omitted; mismatched race/cohort/producer metadata reject adaptation. Zero starts remains valid evidence. Only approved aggregate fields enter review output, so target result fields cannot pass through.

`src/run_brdb_blood_review_field_replay.py` replays a fixed authoritative bundle against the transport-manifest-pinned `BloodReviewDB_CURRENT.zip`. The resolver verifies size/SHA, manifest and Parquet hashes. It checks field batch/single equality and writes aggregate counts only.

## Validation evidence

Command: `PYTHONPATH=/workspace/scratch/brdb-pylibs python -m unittest discover -s horse-racing/brdb/tests -q`  
Result: 38 tests, 0 failures, 0 errors (Python 3.12.14, DuckDB 1.1.3, PyArrow 25.0.1).

Real authoritative input: `horse-racing/jrdb/backtests/BTDAY-0125/20251026/day_prep/RaceNote_20251026/authoritative/race_bundle_20251026_京都1R.json`, input blob SHA `df541481742a28b16e19513cf45c56a7150f4e0b`. The full 9-horse field adapted all 9 P2 role pairs. Review returned 9 records: AVAILABLE 5, AS_OF_UNVERIFIED 4; P2 coverage FULL 5, NONE 4. Batch/single equality passed for all 9. CURRENT generation `eeca93556584a5b8`, pinned ZIP SHA-256 `c0eda6fc55472a4a7a327dcbee6498063bf19209285dfa0b4bc0284ba554305f`.

The result report and exact replay invocation are in `../collab/results/20261022_002_blood-review-v01_verification_result.md`. This validation freezes v0.1 contract semantics; it does not change RRDB, RaceNote, PWA or operational CURRENT.

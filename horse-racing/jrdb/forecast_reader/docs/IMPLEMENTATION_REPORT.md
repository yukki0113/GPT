# Implementation report — Issue #2241

Status: INCOMPLETE. Do not use this as a complete forecast reader.

- Base: `5762281e7ceceb244c54fad9b7abbf5fba38dbaa`.
- Implemented so far: normalized-condition sampler and configurable proposals;
  eight-axis descriptive aggregation over already prepared rows; PACI KYI→ZED
  reader using the common parser; initial CLI plan, input hashes and as-of checks;
  unit tests and a CI workflow. The run path intentionally returns BLOCKED
  until the missing historical adapters and output contract are completed.
- Local tests: `.venv-data-storage/bin/python -m pytest
  horse-racing/jrdb/forecast_reader/tests
  horse-racing/jrdb/tests/test_jrdb_raw_common.py
  horse-racing/jrdb/tests/test_jrdb_raw_history_batch.py -q`: 24 passed.
  The new workflow has not run on GitHub.
- Common data-storage dependency preflight: PASS (DuckDB 1.1.3, PyArrow 25.0.1).
  The canonical `safe_unpack_staged_archive.py` unpacked the Analysis archive
  locally: 48 entries, PASS. No Parquet query or Actions fallback was executed.
- Native Drive folder listing, not keyword search, found both expected inputs.
  PACI261025.zip: 500673 bytes, SHA-256
  `2fcce9418b51b55de3d6ea70e1c73510c24a9daf40047d0d1d6a026ea8847484`.
  On Kyoto 11R, the actual PACI KYI→ZED join was 18/18; horse 8 corners
  [5,7,8,4], horse 13 [1,1,1,1], horse 15 [10,8,1,1]. This validates that
  join only, not the full reader. Analysis archive: 13475200 bytes, SHA-256
  `616c112aeedf8304ace64f94b38d3f4da9e02f5d65071c86e3d2b82f89fb256d`.
  It was modified after the target race; it is not evidence of an as-of snapshot.
- Missing: verified historical condition and class mapping, Analysis historical
  query and previous-history joins, provenance checks for every source, complete
  timezone/metadata and input validation, fallback integration, full runner
  comparisons, leak-proof output validation, atomic evidence/audit bundle,
  integration matrix, full contract, CI execution and completed PR. Added atomic four-file publishing utility and hash test; not yet connected to CLI. No gates are PASS.
- Relevant open PR search (`jrdb forecast`): no results at time of inspection.
- Existing uncommitted work is retained. GitHub publication is a draft; Issue #2241 remains incomplete.

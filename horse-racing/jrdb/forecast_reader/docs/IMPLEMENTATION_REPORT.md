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

## Integrated implementation update

The CLI now connects source SHA/size/version/snapshot verification, common BAC
resolution, canonical Data Storage archive and historical partition routing,
verified condition-export overlays, sampling, previous-history joins, eight-axis
aggregation, PACI previous-run joins, optional common RawHistory fallback,
descriptive runner group comparisons, contract validation and atomic four-JSON
publication. Added strict request keys, post-race snapshot rejection, target-result
output rejection and integration tests. Fixture plan/run reaches PASS and emits
all four files. Identical bundle content is idempotent. Class equivalences remain
UNKNOWN unless established by a verified export; no speculative mapping is added.

Validation: 97 tests passed (Reader, common Raw, RawHistory and Data Storage).
Real canonical Analysis archive was inspected through safe_unpack_staged_archive
and data_storage: 481627 historical rows in 2016–2025. This inspection excludes
2026 partition reads and is not an as-of forecast acceptance. The current archive
is post-race and cannot meet as-of provenance; eligibility/weight/class conditions
also require a verified historical export. Full live evidence remains NEED_INPUT.
The previously recorded PACI join 18/18 remains confirmed.

Remaining acceptance limitations: historical class/date-effective mappings have
not been independently verified; live canonical condition-export acquisition and
Actions fallback E2E are unverified. No completed live forecast evidence is claimed.
PR: https://github.com/yukki0113/GPT/pull/2244 (single existing draft).

# BRDB research generation v0.2 (#2223)

The new builder is `src/build_brdb_research_generation_v02.py`; the legacy
`build_brdb_research_candidate.py` and v0.1 Reader remain unchanged.
Source code/schema/test commit: `8cce021ff02f548870a3b79e11fd7f92e7ea9610`.

## Input and selection contract

The detailed SHA-pinned request is in the approved private artifact at
`generation/build_request.json`. Automatic approval review rejected publishing
the private raw filenames, sizes and hashes as a GitHub input inventory. GitHub
contains the source, Reader schema, aggregate manifest and verification results.
The full request/input inventory is retained in the Drive artifact for replay.

The request binds base and previous generation manifests, the #2220/#2218
artifacts, annual/daily ZIP inventories, cohort counts and exact ID-set SHA-256.
For this run it fixes 27 annual ZIPs (1999–2025), 91 PACI ZIPs (2026-01-04 through
2026-10-25), base `c73cf76ad930b5f0` (128,754 profiles), previous
`f409be3f5d11cb90` (128,858 profiles), 104 preserved daily IDs and 3,794 additional
IDs. Counts are request-bound, not constants in the new Reader.

Annual facts and previous daily facts are retained exactly, including their
source-generation values. Previous selected-source locations are matched back
to the original PACI and inherited. Additional IDs use the latest valid profile
data date, then archive date, ZIP/member/line. Sentinel/future/invalid dates and
parser failures are quarantined; a same-latest-date semantic conflict fails
selection. Every original daily observation is retained in Parquet with ZIP and
member sizes/hashes, line number, raw/semantic hashes, dates and parsed JSON.
Annual selected-source availability is matched back to original UKC records.

Parent relations are recalculated by the existing guarded resolver across the
combined master. Name/year matches alone never establish an ID. All annual and
previous parent-relation differences are exported. Annual-vs-daily review
profiles and semantic histories are exported without overwriting annual facts.

The generation ID hashes the request, source commit, builder/Reader/parser/
resolver/schema/storage source hashes, source manifests, selection contract and
DuckDB/PyArrow versions. Output location and wall-clock time are excluded. A
private staging directory and exclusive generation lock protect publication;
existing generations are never overwritten.

## Reader

`src/brdb_research_reader_v02.py::ResearchGenerationReader` accepts an explicit
generation path. The manifest extension is documented by
`schema/brdb_research_reader_contract_v0_2.schema.json`.

It verifies the added count, annual count, exact ID sets, bound audit/history
file SHA-256 values and selected-source metadata against the real fact rows.
Daily profiles remain hidden before their selected observation date. Annual
latest profiles also require their actual source observation/profile date.
Parent IDs with unavailable parent profiles are suppressed as UNKNOWN.
Comparisons are date inclusive; publication time within the day is unknown.
Historical reconstruction from earlier daily records is not implemented.

For legacy v0.1 manifests the wrapper delegates to the original 104-ID Reader,
retaining its original behavior. New v0.2 manifests cannot fall back to that
legacy guard when their contract is absent or invalid.

## Replay

Materialize the exact approved inputs with connected Drive tools or existing
verified immutable artifacts. Never introduce authenticated Drive transport into
Actions. Use the shared `tools/data-storage/` environment (DuckDB 1.1.3); the
verified run used PyArrow 25.0.1 and Python 3.12.14.

The detailed ZIP supplies the request. The source artifacts required alongside
it are the original base, previous candidate and
`issue2220_missing_3794_causes_20261027.zip`, plus the SHA-pinned raw ZIPs.
The #2220 artifact also embeds the fixed #2218 population audit. Base can be
materialized with the existing annual builder and all 27 original ZIPs if needed;
its manifest must match the request before v0.2 will accept it.

```bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python \
  horse-racing/brdb/src/build_brdb_research_generation_v02.py \
  --request generation/build_request.json --base base --previous previous \
  --cause-audit issue2220_missing_3794_causes_20261027.zip \
  --annual-dir annual --paci-dir paci --output-root first \
  --source-commit 8cce021ff02f548870a3b79e11fd7f92e7ea9610
```

Run the same command with a separate `--output-root second`, retaining the same
request/source commit. Then verify actual outputs and the fixed KYI population:

```bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python \
  horse-racing/brdb/src/verify_brdb_research_generation_v02.py \
  --generation first/brdb-pedigree-research-v02-5279af0bd8226cde \
  --repeat second/brdb-pedigree-research-v02-5279af0bd8226cde \
  --request generation/build_request.json --base base --previous previous \
  --cause-audit issue2220_missing_3794_causes_20261027.zip \
  --annual-dir annual --paci-dir paci --output verification
```

Focused regression command:

```bash
PYTHONPATH=tools/data-storage:horse-racing/brdb/tests \
  .venv-data-storage/bin/python -m unittest \
  test_brdb_research_generation_v02 \
  test_brdb_research_candidate.CandidateSelectionTest -v
```

The verifier independently checks source observation records, all annual/old
facts, relation differences, generation identity, byte-identical rebuild,
3,898 single/batch profile queries and old 104-ID single/batch compatibility.
It replays the same 10,680-horse/39,543-declared-entry KYI denominator and uses
the real new Reader for each date. All pedigree/official-lineage/parent-ID/depth
metrics distinguish static and as-of scope. KYI declarations do not confirm
actual starts or cancellation status. Results do not extend beyond 2026-10-25.

The artifacts are research outputs. No live CURRENT pointer, PWA, RaceNote,
Newspaper or production workflow is changed. No Actions run is claimed for the
managed-runtime execution.

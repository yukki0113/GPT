# Reproduce the 2026 race-year pedigree audit (#2218)

The audit reads 91 fixed 2026 PACI ZIPs dated 2026-01-04 through 2026-10-25.
The denominator is KYI declarations linked to a same-day BAC race, keyed by
race date / race key / horse number. Conflicting duplicates, invalid identity,
invalid lengths, missing ZIP/member, or SHA mismatch fail the audit. Identical
entry duplicates are removed and counted. Cancellation and actual-start status
are UNKNOWN from these pre-race inputs; declarations are retained.

Check out source code commit `8ac6879fb5e66afddcfccea5440b7fb631145fc4`.
Use the shared `tools/data-storage/` bootstrap and pinned DuckDB environment.
Materialize the exact approved inputs using connected Drive tools or previously
verified immutable artifacts. The package's input manifests and SHA-256 values
are the reference; downloading authenticated Drive inputs through Actions is
not part of this audit.

Required input layout (local paths supplied explicitly):

- `paci/`: the 91 ZIPs from `inputs/paci_source_manifest.json`.
- `annual/`: all 27 original annual UKC ZIPs, 1999–2025.
- `base/`: validated generation `c73cf76ad930b5f0` (128,754 profiles).
- `research/`: validated candidate `f409be3f5d11cb90` (128,858 profiles).
- `current/`: read-only extracted CURRENT `eeca93556584a5b8`, including its
  existing `current.json`; this is a local audit input, not the live pointer.
- `inputs/missing_108_audit.json`: the fixed #2212 exact-ID audit.

From the repository root, with those inputs available:

```bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python \
  horse-racing/brdb/src/audit_race_year_pedigree.py \
  --paci-dir paci --annual-dir annual \
  --inventory inputs/paci_source_manifest.json \
  --base base --research research --current current \
  --missing-audit inputs/missing_108_audit.json \
  --output audit_result \
  --source-commit 8ac6879fb5e66afddcfccea5440b7fb631145fc4
```

Run the representative regression tests:

```bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python -m unittest discover \
  -s horse-racing/brdb/tests -p test_audit_race_year_pedigree.py -v
```

The artifact also includes `verify_outputs.py`. Running it with the audit output
path verifies output hashes, reaggregates horse and entry CSVs against JSON,
checks monthly denominators, and checks observed-date guards:

```bash
python verify_outputs.py audit_result
```

Static horse coverage uses unique horse IDs. Entry coverage retains repeat
appearances. As-of horse coverage is evaluated at each horse's earliest scanned
entry; separate any-entry and every-entry counts are also reported. Monthly
horse cohorts are unique within each month. The optional A1/A2 group identifies
horses whose first scanned appearance is in a declared new/unraced race; it does
not prove a real-world debut independently.

The latest research reader suppresses a selected latest snapshot before that
snapshot's selected observation date. Annual cohort profiles are matched to
original records by exact ID, profile date and semantic hash. Other annual
ancestor profiles use a conservative verified pre-2026 source-date bound.
Each as-of graph edge requires both child and canonical parent profiles to be
available. Within-day publication times are unverified. The overall graph uses
sire/dam edges; direct sire/dam is generation 1, direct BMS is generation 2.
Depth 0 includes unmatched horses and unresolved branches; it does not prove
an ancestor's absence.

All result files are research outputs. No live CURRENT or production consumer
is written. Execution evidence is a full managed-runtime run and checksummed
artifact; no GitHub Actions job is claimed.

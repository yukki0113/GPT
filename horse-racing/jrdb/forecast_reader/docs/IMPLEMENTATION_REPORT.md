# Issue #2241 implementation and acceptance report

Status: INTEGRATED; full live acceptance NEED_INPUT. Issue is not claimed closed.
PR: https://github.com/yukki0113/GPT/pull/2244
Branch: codex/issue2241-forecast-reader
Base: 5762281e7ceceb244c54fad9b7abbf5fba38dbaa
Integration commit: 69850ab2b1bd48ff21c0ed4daf04534ac6576dc8

## Delivered

CLI plan/run, request validation, SHA/size/kind/version/snapshot validation,
BAC target/assertion resolution, configurable exact/supplement sampling,
canonical Analysis archive/partition query routing, verified normalized condition
exports, prior-history joins, separate eight-axis frequency tables, KYI→ZED
joining, optional declared common RawHistory SED fallback, descriptive runner
comparisons, strict date boundaries, output validation, deterministic atomic
four-JSON publishing, evidence contract, README and CI.

Class equivalents and renamed races are never inferred. Unverified mappings
remain UNKNOWN and require a verified export. S1/S2/S3 windows 21/42/70 and one
representative per year are proposed config defaults. Tests cover stage windows,
5/4 branching, empty stages, year representatives, multiple-per-year mode, leap
calendar, exact eight Kyoto/two Hanshin exclusion, unknown old/new class codes,
previous result joins/duplicates/future dates, output hashes and target-result
rejection. Fixture CLI inputs reach PASS and publish all four JSON files.

## Validation

Local command:
`PYTHONPATH=tools/data-storage .venv-data-storage/bin/python -m pytest horse-racing/jrdb/forecast_reader/tests horse-racing/jrdb/tests/test_jrdb_raw_common.py horse-racing/jrdb/tests/test_jrdb_raw_history_batch.py tools/data-storage/tests -q`

97 passed. Common check-deps PASS: DuckDB 1.1.3, PyArrow 25.0.1.
GitHub PR CI PASS on integration commit:
https://github.com/yukki0113/GPT/actions/runs/41021178701

Canonical entrypoints: tools/data-storage safe_unpack_staged_archive.py and
Python data_storage.query.execute_query; execution local, not Actions fallback.
Native Drive direct folder listing found both expected inputs; keyword search
zero results were not treated as nonexistence. No data bytes entered Git.

PACI261025.zip: 500673 bytes, SHA256
2fcce9418b51b55de3d6ea70e1c73510c24a9daf40047d0d1d6a026ea8847484.
Real Kyoto11R KYI→ZED 18/18; horse8 [5,7,8,4], horse13 [1,1,1,1],
horse15 [10,8,1,1]. These confirm previous-run joins only.

Analysis current: 13475200 bytes, SHA256
616c112aeedf8304ace64f94b38d3f4da9e02f5d65071c86e3d2b82f89fb256d.
Common safe unpack PASS (48 entries). Canonical queries read 481627 historical
rows from the manifest-declared 2016–2025 partitions, excluding 2026 partition
reads. This inspection is not a completed as-of forecast.

## Unresolved acceptance prerequisites

The obtained Analysis current is a post-race generation modified 2026-10-26;
it cannot establish an as-of 2026-10-25 snapshot. Analysis Lite also lacks fully
verified class/eligibility/weight conditions. A verified historical condition
export and as-of historical generation are needed for a live evidence PASS.
No fabricated S0 live count, mapping or historical availability is claimed.
The old/new class date-effective mapping is unverified. Actions fallback live
E2E has not been run for this Reader because local canonical dependencies work;
its existing routing is documented, not claimed tested here. Canonical source
acquisition must be performed externally through native Drive metadata and SHA
pinning. Neither snapshot timestamps alone nor a link-sharing flag proves it.

Pending merge: this single draft PR; no production policy/model changes and no
merge or direct main publication. Existing local uncommitted work is retained.

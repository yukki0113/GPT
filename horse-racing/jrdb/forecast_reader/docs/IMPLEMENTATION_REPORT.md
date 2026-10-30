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

## Review correction — issuecomment-6518067970

Implemented separate cohort and reference-history inputs. `reference_rows` and
verified `jrdb.history.references` permit 2015 previous runs for 2016 starts without
adding 2015 starts. Duplicate (race_key,horse_id), non-earlier previous dates,
missing expected cohort years and missing previous joins are audited/rejected or
PARTIAL. Archive routing now checks partition-year uniqueness, bytes, SHA, row
counts and year membership. Condition exports still require complete coverage and
source provenance; incomplete Lite conditions continue to return NEED_INPUT.

Completed all eight runner comparisons: KYI base_win_rank (pre-race only), UKC
calendar age and sire, frame/style/jockey and previous distance/class. Every axis
has explicit unknown reasons. membership_only and explanation distinguish observed
group membership from favorable suitability; linked starts/finishes/top3 evidence
is retained. Static style and previous corners are not substituted. UKC identity
joins are keyed by horse_id, not name.

Source snapshot_at alone is now rejected. Stable before/after native metadata,
observation identifier, provider, revision/version and download SHA bindings are
required and recorded. Caller must supply authentic connector evidence; Reader
does not authenticate arbitrary JSON. Recursive output scanning also covers source
and sampling audits and nested keys. Only direct runner previous_run finish is
allowed; final popularity/odds/payouts are forbidden throughout outputs. Tests
assert target SED/HJC/SRB acquisition is never requested by PACI previous reader.

Real measurements after correction (same input SHAs above): Kyoto named/distance
candidates 8 races, 143 starts; other venue 2 races. These are NOT verified S0,
because eligibility/weight/class and as-of conditions remain unverified. Seven
statistical axes have 143/143 starts (popularity 18 groups, frame 8, style 4, age 1,
sire 53, jockey 48, previous distance 7); previous class has 143 missing. Previous
distance join 143/143. Real PACI previous joins remain 18/18; UKC age and sire
coverage are each 18/18. No live PASS is claimed.

Source investigation: common BAC parser and existing accepted Warehouse adapter
were inspected. Canonical Warehouse path is
GPT/horse-racing/10_warehouse/jrdb/v1/current.json (2010–2025), BAC family keyed by
race_key; needed columns are race_class_code, grade_code, race_type_code,
symbol_code, weight_rule_code, turn/layout and race date. Lite projection cannot
supply full eligibility/weight conditions. A provenance-pinned BAC family/export
covering these keys is still needed, plus earlier reference rows where unavailable.

Official 00_document folder was directly listed:
https://drive.google.com/drive/folders/1Net_dx_CNHL_fMekneShkhRKJZdJ5SCh
Its jrdb-specifications-oneshot-20261015.zip was retrieved (1762089 bytes, SHA256
79bbdf124caafe77e486d68116474713e9b71dda8ee17ce536fc0031fd7b8000).
004_bac_doc.txt confirms condition fields and refers to the JRDB code table.
128_jrdb_code.txt is dated 2019-05-26 and describes the class-label change; code 16
is listed as 3-win with old label 1600man. This revision date alone does not prove
race-level effective dates or historical code validity for every prior year.
No unsupported date-effective equivalence was added. A dated historical code
specification/verified mapping plus BAC evidence remains the prerequisite.

Regression scope added: 2016→2015 reference join, reference duplicate/future checks,
missing-year audit, eight-axis reasons and counts, metadata-only timestamp rejection,
stable metadata mismatch, nested source-audit leak rejection, permitted historical
previous finish, no target-result archive access and canonical bundle hash equality.
Final local test command is the full Reader/Raw/RawHistory/Data Storage command
above. One earlier run hit the existing randomized ciphertext-corruption test
(test_drive_gpt_actions_bridge.py) once; no production/test changes were made there,
and a complete rerun passed. Updated CI results are linked in the PR.
Draft remains required until the unresolved real-data prerequisites are met.

Correction validation: full local suite 107 passed in 2.23s.

Review CI: commit 375134028fb7ce2fc3ab6232979c69704e4b228b push check
https://github.com/yukki0113/GPT/actions/runs/41025188480 succeeded.
Previous-class comparison additionally remains unknown unless normalized_class
is explicitly verified, preventing raw OP codes from being compared as equivalent
to normalized OP/grade groups. Invalid provenance timestamps report UNVERIFIED_AS_OF.

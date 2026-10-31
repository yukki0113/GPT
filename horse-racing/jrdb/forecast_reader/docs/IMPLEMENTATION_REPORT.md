# Issue #2241 implementation and acceptance report

Status: latest菊花賞2026 live acceptance PASS (see final acceptance section); earlier NEED_INPUT entries below are retained as dated work history. No main merge.
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

Final reviewed code commit: e2f016f765dc8830b14c8eacf620d6d9a0bf982a.
Final PR CI PASS: https://github.com/yukki0113/GPT/actions/runs/41025343509
Final push CI PASS: https://github.com/yukki0113/GPT/actions/runs/41025336594
Local final regression: 107 passed in 2.47s; Reader-only follow-up 35 passed.

## Final acceptance — BAC Warehouse and pre-race generation reconstruction

Supersedes earlier NEED_INPUT for the tested 2026-10-25 Kyoto11R case. No source
conditions were guessed and no post-race current generation was used as authority.
The standard forecast_reader_runner.py --run completed with status PASS.

1. Accepted Historical Warehouse final manifest was fetched natively and inspected.
   BAC 2015–2025: 11 immutable Parquet assets, 37949 race conditions, exact manifest
   SHA and byte-size verification plus row counts and year coverage. Condition
   normalization reuses the shared BAC field contract. All ten 菊花賞 instances
   have matching OP:1, 12:541, turf/3000 and weight=3; eight are Kyoto outer and
   two (2021/2022) are Hanshin. The latter are excluded. Exact keys:
   08164711,08174711,08184711,08194711,08204611,08232711,08245611,08253911.
2. The official 2019-05-26 code table explicitly lists condition code 16 as current
   3-win and old label 1600man. Verified labels/source SHA are now configured.
   Matching uses the unchanged raw condition code AND grade identity. Distinct
   codes 15/16 are not collapsed even though both have group=3. A calendar label
   change date is not inferred from the specification's publication date; no
   economic-rule equivalence across different raw codes is claimed. Unknown codes
   remain UNKNOWN. This is sufficient for the tested OP:1 exact comparison and
   preserves raw-code identity across the old/new label change.
3. BAC has 53 gaps in December 2025 relative to the Analysis pool. Accepted SED
   year=2025 supplies the published race-condition fields for exactly those keys.
   It is read through common Data Storage with a condition-only projection, not
   finish/popularity/payout columns. Consistency across horse rows is checked.
   Full Analysis-pool condition coverage is thereby obtained without inventions.
4. Pre-cutoff Analysis generation found on native Drive:
   analysis-v1_4-postrace-20261018-01. Manifest created 2026-10-19T01:00:20.977099Z,
   Drive modified 2026-10-19T01:03:58.649Z, before as_of 2026-10-25T15:30+09:00.
   Its 2016–2025 partition SHAs are identical to the already materialized bytes.
   Reader now accepts an immutable generation manifest rooted with its assets;
   every referenced prior-year file is rechecked for SHA/bytes/row count/year.
   No 2026 Analysis partition is opened. Reusing identical bytes is not treating
   the newer current pointer as historical authority.
5. Real CLI request/input observations are in work/issue2241-live-{request,inputs}.json.
   Native before/after listing checks for BAC assets, manifests and PACI were
   stable. Native revision IDs were not exposed, so metadata version remains null;
   generation IDs and immutable manifest SHA/asset bindings supply content identity.
   Full ten-year input: 481627 starts/34548 races; selected cohort: 143 starts/8 races.
   Previous joins required/joined: 143/143; missing 0. The two coverage populations
   are now explicitly separated. Unselected-pool missing references do not silently
   inflate selected-cohort missing counts; neither do they add statistical starts.
6. Eight historical axes all have 143 valid starts and zero missing. PACI runners
   18/18 previous joins and 18/18 UKC age/sire; all eight runner comparisons have
   values and evidence, no unknowns for this case. Previous classes use verified
   code/grade identity with BAC/ZED disagreement rejected. Previous corners for
   horses 8/13/15 remain [5,7,8,4], [1,1,1,1], [10,8,1,1].

Real Evidence Bundle generated twice from identical inputs: all four files are
byte-identical. Manifest request SHA:
9cdbfd1fda503a5bf56e5128da57d70e1c351fc9c61aea667e5887e613bdf8df.
Code/config SHA: 2b711447ad8a3fbf7347e93c17a72aec3ea56ade38eb7d9a5858bc8fb4ecefd3.
Output SHAs:
- forecast_evidence.json: 4238ede7ae55d8cf11c9804f4bbfe6b78747d029dc68ea148771456d6b570960
- sampling_audit.json: 06272eeeb5028913d25c495aa4baaefbb1da4c7021f723962f96aafd56af7baf
- source_audit.json: 589b394573d28d91744c76485f4c058fdd49e353b595d8398574b03af7cb71b1

Files remain local in work/issue2241-accepted-final/<request-sha>/ and compressed
in work/issue2241-kikuka-evidence.zip; no underlying datasets are committed.
The source audit includes each consumed BAC/SED/Analysis asset SHA and manifest
provenance. SED2025 SHA: 6a7be1dc005833c9caaa20559ac3ad40af99bdc95a342b0e57d638ca979f8974.
Execution route: local, existing canonical tools/data-storage. No fallback needed.

Local regression: 111 passed (Reader, Raw, RawHistory, Data Storage). New tests
cover immutable BAC coverage/hash rejection, condition-only SED fallback, distinct
class code identity, and separation of selected cohort from unrelated history.
CI now runs the same common dependency and test scope. CI URL is recorded below
when the existing PR branch finishes its checks. PR remains #2244; no main merge.

Limits: this establishes the named G1 case. It is not evidence that every historical
race, code-change date, every 3-win renamed special, or every future date has valid
inputs. Missing sources/unknown code/date mappings still fail closed. Earlier
2015 references for other selected cohorts can be reconstructed from the accepted
2010–2025 Warehouse using existing adapters if they are needed; they were not
required by the selected 143 starts here. No missing-value imputation was used.

Authority manifest SHAs (native observations retained in local input receipt):
- jrdb.paci.daily: 2fcce9418b51b55de3d6ea70e1c73510c24a9daf40047d0d1d6a026ea8847484; PACI261025
- jrdb.analysis.current: f8627085b9ff905166a8b6c51f842bdc382d2a3529b11fb72086d41b843f5557; analysis-v1_4-postrace-20261018-01
- jrdb.historical_conditions: 62fb6eb79546e3e0dd2b70592e0324d52c33c361f7073e78c2b420b82e1e008d; jrdb_normalized_warehouse_v1_2010_2025_g20260921

Final acceptance code commit: b999d255a2edb8701953883dc7495031e4add9f0.

Final acceptance CI PASS on b999d255a2edb8701953883dc7495031e4add9f0:
- PR: https://github.com/yukki0113/GPT/actions/runs/41151757778
- push: https://github.com/yukki0113/GPT/actions/runs/41151752158
Native observations were taken during this investigation; the provider's recorded
publication/modified times and immutable old-manifest content bindings establish
pre-cutoff availability. We do not claim that this agent observed the files at the
historical prediction time. Existing source receipts are preserved locally.

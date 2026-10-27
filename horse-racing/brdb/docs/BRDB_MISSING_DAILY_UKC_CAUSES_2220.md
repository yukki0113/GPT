# Reproduce #2220: missing 2026 KYI pedigree causes

Source code/tests: `2b35a85aa213b34de26d0ebc7117e7812ec2a990`.
This is a read-only source/cause audit, not a generation build.

## Inputs

- Exact #2218 ZIP `issue2218_race_year_pedigree_audit_20261027.zip`, SHA-256
  `e3e5ee8b7eca9c0b1bd17d648683307aee52d6b9922266da491eb1d6b7e0089b`.
  A byte-identical copy is included under `inputs/` in the #2220 artifact.
- Its `inputs/paci_source_manifest.json`: 91 SHA-pinned PACI ZIPs dated
  2026-01-04 through 2026-10-25, materialized in `paci/`.
- Its `audit/annual_inventory.json`: all 27 original annual UKC ZIPs,
  1999–2025, materialized in `annual/` with exact sizes/hashes.
- Candidate `f409be3f5d11cb90`, including all manifest-referenced files,
  materialized in `research/`. The existing approved
  `issue2214_brdb_research_candidate_f409be3f5d11cb90.zip` supplies it.

Use connected Drive tools for private acquisition. The audit does not import
Drive credentials into Actions, fetch unapproved sources or alter raw ZIPs.
Use the shared `tools/data-storage/` environment/bootstrap, including DuckDB
1.1.3. The verified run used Python 3.12.14 and PyArrow 25.0.1.

From the repository root:

```bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python \
  horse-racing/brdb/src/audit_missing_daily_ukc_causes.py \
  --upstream inputs/issue2218_race_year_pedigree_audit_20261027.zip \
  --paci-dir paci --annual-dir annual --research research \
  --output missing_cause_result \
  --source-commit 2b35a85aa213b34de26d0ebc7117e7812ec2a990
```

The upstream ZIP checksum, all internal checksums, 10,680-horse/39,543-entry
population, 6,886 joined horses and 3,794 unique missing IDs are revalidated.
The 292 as-of-only blocked entries of already-joined horses are not in this
static missing cohort. The KYI/BAC denominator is replayed with existing
parsers and checked against #2218. Actual start/cancellation status is UNKNOWN.

Each annual/daily UKC source is checked by archive/member/record counts and
SHA-256. All record identities and lengths are scanned. Full UKC parsing is
needed only for exact target-ID matches; this is not a complete field-quality
audit of unrelated annual records. Three old annual source identifiers outside
the numeric KYI domain are recorded without normalization or name matching.
The scan proceeds beyond them and checks the full 1,312,543 annual records.

Primary reasons are mutually exclusive; evidence flags are not. Missing input
or parsing failure remains UNKNOWN. Profile sentinel/calendar/future-date and
same-latest-date conflict guards use the candidate's selection contract.
Birth years require consistent valid birth dates in exact-ID UKC evidence.
First-appearance month groups are disjoint; active monthly horse groups can
overlap. BAC A1/A2 identifies a declaration class, not a proven first start.

## Validation

```bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python -m unittest discover \
  -s horse-racing/brdb/tests -p test_audit_missing_daily_ukc_causes.py -v
```

The detailed artifact contains `verify_missing_causes.py`. It independently
reaggregates CSV/JSON totals, checks monthly denominators against #2218 and
reads all 10,016 matching raw source records again, verifying exact ID,
ZIP/member/line, raw/semantic hashes and parsed fields:

```bash
PYTHONPATH=horse-racing/jrdb/src python verify_missing_causes.py \
  --audit missing_cause_result --paci-dir paci \
  --upstream inputs/issue2218_race_year_pedigree_audit_20261027.zip
```

## Output and next-build interpretation

`missing_3794.csv/json` contains one primary reason and evidence flags for each
horse. `source_observations.jsonl/csv` retains exact raw-source provenance.
`entry_evidence.csv` separates dated raw evidence from conditional eligibility
of the latest selected profile. Cross tables cover first month, active month,
source birth year, declared new-race class and BAC type/class/surface. Empty
UNKNOWN lists remain explicit. Summary, error inventories and the output
manifest distinguish complete scope from input gaps.

The measured source-supported improvement is +3,794 horses/+10,016 entries.
This would reach all 10,680 horses/39,543 entries in this fixed static cohort.
A separately built master preserving the annual facts and existing 104 overlay
would have 132,652 profiles. It requires the same 27 annual ZIPs and all 91
daily UKC members, with the inclusion filter expanded beyond the old 104 IDs.
Parent relations, regression and explicit research-reader behavior still need
validation in that separate build. This Issue performs no such build.

Under that preservation assumption a single-latest-profile candidate could
add 3,794 date-safe entries (total 33,029/39,543, 83.526794%). Dated source
records support all 10,016 missing entries, but historical reconstruction is
not implemented by the current Reader. Those two quantities must not be
interchanged. Comparisons are date inclusive; intraday publication times are
unverified. Coverage outside the fixed inventories/period is UNKNOWN.

# BRDB 27年UKC 日付・最低限の系統利用方針 — 2026-10-23

Status: SENTINEL SOURCE ROOT CAUSE CONFIRMED / CANDIDATE AUDIT RUNNING
Production: NO CUTOVER. CURRENT remains `eeca93556584a5b8`.

## Raw source inspection

Inputs: all `UKC_1999.zip` through `UKC_2025.zip` (27 archives), full raw record count 1,312,543. UKC parser offsets: `data_date` bytes 268..275 (0-based), `sire_line_code` 276..279, `broodmare_sire_line_code` 280..283.

Exactly **8** raw records have `data_date = 99999999`, all stored in `UKC_1999.zip / UKC999999.txt` and associated with eight distinct horses. No other archive has that value. The listed horse IDs are:
`04102987`, `03102837`, `00107542`, `02102324`, `99107052`, `96107396`, `99107004`, `03102976`.

All eight identities were independently found again in the 27-year raw input with genuine 8-digit observation dates; latest actual dates per horse (before ignoring 99999999):

| horse_id | latest real data_date |
|---|---|
| 04102987 | 20100829 |
| 03102837 | 20080203 |
| 00107542 | 20051218 |
| 02102324 | 20060402 |
| 99107052 | 20050403 |
| 96107396 | 19991107 |
| 99107004 | 20051120 |
| 03102976 | 20081018 |

**Important:** The original v0.1 generator checks only `\\d{8}` and chooses `max(data_date)` lexically. Therefore, for each of the eight horse IDs, a sentinel row takes precedence over actual dates. The 27-year comparison generation `9ad752020bd5801b` is useful for coverage research but should **not** be promoted unchanged to CURRENT. 99999999 is *not a valid chronology timestamp*. Its historical business semantics remain unverified; do not claim it denotes a current/future or specific official status.

Acceptance before a new production candidate:
1. Explicitly quarantine invalid/sentinel date records in the generation builder, recording `archive/member/horse_id/raw_date` and preserving raw byte receipts.
2. Make filtering/version semantics part of a *distinct* generation identity and manifest; do not silently regenerate different bytes under `9ad752020bd5801b`.
3. Test selected profile for all 8 horses resolves to actual latest valid date, historical `as-of` guard remains fail-closed, and past v0.1 CURRENT unchanged.
4. Rerun 27-year lineage, parent resolution and 2025-depth-coverage comparisons on the corrected immutable research candidate.
5. Require an independent cutover review; no PWA/Newspaper change.

## Minimal lineage objective

The user's minimum acceptance target is **official sire and broodmare-sire line names**, not complete 5-generation ancestry. JRDB UKC provides two lineage codes natively; the project-approved JRDB `code__keito` master maps them to major/minor names. Previous 27-year generation audit shows **78 observed lineage codes, all 78 mapped**. Mapped-code equality is not the same as per-horse coverage; quantify nonempty codes and real archive cohort on issue #2171.

Suggested evidence projection:
```json
{
  "horse_id": "...",
  "sire_line": {"code": "...", "major_name": "...", "minor_name": "...", "evidence": "JRDB_CODE"},
  "bms_line": {"code": "...", "major_name": "...", "minor_name": "...", "evidence": "JRDB_CODE"},
  "sire_region": {"value": "UNKNOWN", "basis": null},
  "maternal_region": {"value": "UNKNOWN", "basis": null},
  "coverage": {"official_lines": "FULL|PARTIAL|NONE", "regional": "UNKNOWN"},
  "provenance": {"generation": "...", "taxonomy_version": null}
}
```

Neither code nor breeding place establishes Japanese/US/European pedigree ancestry. Geography classification requires a reviewed, separately versioned `lineage-root-taxonomy` with definitions, multiple-origin and UNKNOWN cases and source evidence. **Do not** label `米国型` based on the existence of e.g. ミスタープロスペクター系 without reviewed mapping. Until taxonomy approval, use `UNKNOWN` instead of guessing.

## Unresolved years

Issue [#2171](https://github.com/yukki0113/GPT/issues/2171) computes status and parent birth-year frequencies from the isolated 27-year candidate, plus per-horse lineage completeness and sentinel profile detection. Results require artifact verification; do not copy old 16-year missing counts as 27-year results.

## Accepted Actions audit result — Issue #2171

Run [39941621679](https://github.com/yukki0113/GPT/actions/runs/39941621679), PASS, source commit `012bb1b2042caac2bdebc2a34aec342a9dcda8e3`, output `brdb_27year_date_lineage_audit.json`, source generation `9ad752020bd5801b`.

- Total 128,754 pedigree fact horses.
- Official master contains 83 available codes. Sire-line: 128,746 nonempty and **all 128,746 mapped** (8 unknown). Broodmare-sire-line: 128,749 nonempty and **all 128,749 mapped** (5 unknown).
- Eight profile rows use invalid chronology `99999999` (same eight IDs in raw). This **demonstrates actual selection contamination** in candidate and blocks promotion before new candidate generation.
- Unresolved parent relations (counting all sire, dam and BMS relation slots across **all** 128,754 horses; NOT unique ancestors):
  - born before 1990: **122,323**
  - 1990–1999: **81,884**
  - 2000–2009: **27,605**
  - 2010–2025: **7,588**
  - year unknown: **9**
  - total **239,409**.
- Direct unresolved relation-status counts: sire NO_CANDIDATE 66,760, dam NO_CANDIDATE 66,980, BMS NO_CANDIDATE 105,429, plus smaller conflicts/insufficient key/guard. The 27-year master covers more total horses than the original 16-year master, so this all-master unresolved count **must not** be compared naively as a progress measure; compare the same target IDs / depths.

**Acceptance revision:** do not block minimum official-lineage research on 3–5 generation completeness. Profile chronology quarantine applies to these 8 candidates; use official codes for source-backed father/BMS line reporting and UNKNOWN for regional type pending reviewed taxonomy. `brdb-review-v0.1`, CURRENT and shared PWA are untouched.

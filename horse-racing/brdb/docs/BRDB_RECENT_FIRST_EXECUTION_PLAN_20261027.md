# BRDB 2205原因対応・今後の実施設計（2026-10-27）

Status: DESIGN APPROVED AS WORKING PLAN / FIX REVALIDATION PENDING
Boundary: no BRDB CURRENT cutover, no RaceNote/Newspaper/PWA production edits.

## 1. Issue #2205 root cause

- [#2205](https://github.com/yukki0113/GPT/issues/2205) / run [40424240372](https://github.com/yukki0113/GPT/actions/runs/40424240372) failed in first `brdb-regression-tests` step. No 27-year candidate was built.
- Artifact `stderr/01-brdb-regression-tests.log` shows `SyntaxError: unexpected character after line continuation character` at `build_brdb_pedigree_generation.py:103`.
- Root: literal text `\\n` remained inside the newly inserted `99999999` quarantine block. Two import-time errors, `test_brdb_ukc_date_sentinel` and `test_build_brdb_pedigree_generation`; all other 63 tests passed.
- Narrow repair: commit `1f634b7821c73aa1fc3ea9e89a89885ce1612552`; follow-up run [#2206](https://github.com/yukki0113/GPT/issues/2206) for full suite and isolated 27-year research build, comparison and lineage audit.
- **Do not claim success** until the #2206 job concludes PASS and generation artifact plus quarantine count and final profile dates are read back.
- The prior 27-year research generation `9ad752020bd5801b` is quarantined for promotion. It selected 8 source `99999999` rows; the source ZIPs remain immutable.

## 2. User's outcome-based priorities

### P0: 2–3 newest seasons (2024–2026)

**Goal**: each actual current race entrant identified by JRDB `horse_id` gets usable source-backed father, mother, BMS names and father/BMS official lineage; missingness and as-of provenance visible. Require actual 2026 UKC/current entry source before asserting current-year pass. 5-generation completeness **not required**.

Report for each race year: entrants unique, starts, joined horse IDs, sire/dam/BMS-name-present, sire/BMS-lineage-code-present, lineage-code-official-master-mapped, profile-as-of-safe; count and percentage denominator explicit. No birth-year cohort substitution for race-year population.

### P1: 10 seasons (2016–2025)

**Goal**: stable horse_id joins between pedigree and historical JRDB Analysis / RaceNote competition facts. Preserve `race_date < target_date` when generating backtest features and evidence. Record time-of-observation dates and handling of archives with later profile snapshots. Show annual join coverage and conditions (surface, distance, going, venue, year, class), with pre-registered minimum sample and baseline for statistical segment queries.

Only commence trend conclusions after consistency tests (same horse across seasons, no forward result contamination, no duplicate-starter distortion).

### P2: older ancestors and regional root

**Goal**: targeted 3–5 generation **ancestor presence**, e.g. `paternal_branch includes Storm Cat` or `maternal_branch includes Halo`; not fully populate pre-2000 race results. Separate `father IS Storm Cat` from `sire-branch ancestor Storm Cat`; separate maternal `any D-prefix path` from pure tail-female `DDD...` path and `BMS-lineage is Halo-line`. Canonical ancestor ID/evidence/version mandatory for factual ancestor presence. Absence cannot be proven on incomplete paths.

Region-type `US-root`, `Europe-root`, `Japan-developed` must be a reviewed, multi-label taxonomy with explicit source/date, version and UNKNOWN. JRDB official lineage code is not a country code; do not auto-map from horse name or birthplace.

## 3. Execution order and acceptance gates

| Order | Work package | Required inputs | Output/acceptance |
|---|---|---|---|
| 0 | #2206 verify date correction and fixed generation | 27 pinned ZIP, builder v0.2.0 | all tests PASS; exactly 8 quarantined; zero sentinel selected; distinct generation ID; manifest and hashes PASS; no CURRENT change |
| 1 | Source inventory + race-year cohort definition | 2024–2026 current entry source, Analysis/RaceNote source | exact scope, keys, available data date, licensed/raw source mapping; 2026 unverified explicitly |
| 2 | P0 latest-field audit | verified candidate, yearly target horse IDs | annual rates for names, codes, mapped labels and as-of; confidence in joining; exception horse list |
| 3 | P1 10-season audit | historical 2016–2025 entries/results + candidate | year-by-year horse ID join and chronology validation; regression of 2024–2025 cohort stability |
| 4 | Official-lineage minimal evidence contract | `pedigree_fact` + `lineage_code_master` | deterministic sire/BMS projection with coverage/provenance and UNKNOWN flags; no scoring |
| 5 | Regional ancestry dictionary v0.1 | approved pedigree origin/source references | reviewed classification for high-frequency families, provenance, no forced country |
| 6 | Presence-of-ancestor PoC | as-of-safe resolved ancestors + vetted supplemental canonical IDs | true/unknown/false semantics, branch and generation paths, no fuzzy IDs |
| 7 | Conditional performance research | year-audited starter facts + taxonomy | non-predictive sire/BMS × conditions cohorts, baseline, sample counts, chronological holdout |
| 8 | Optional Review v0.2 candidate | all above audited | separately versioned contract and human approval before UI; v0.1 remains frozen |

### Stop rules

- Do not spend cycles filling unknown ancient ancestry if P0 or P1 misses a basic name/lineage coverage gate.
- Do not use 3–5 generation graph FULL as P0/P1 acceptance.
- Do not infer 2026 UKC availability from 1999–2025 ZIP inventory.
- Do not select newer profile observations as historical features without explicit as-of verification.
- Do not silently promote a research generation to CURRENT or deploy to shared PWA.
- If #2206 fails, retain error artifact and fix the exact failing step before continuing with candidate acceptance.

## 4. Practical product deliverable

After P0/P1: read-only view per entrant with sire, dam, BMS, sire major/minor line, BMS major/minor line, confidence/coverage and source date; then an observational cohort finder such as `sire_family=Sunday × bms_regional_root=US × dirt 1400–1800m` with outcome samples and matched baseline. An ancestor-presence filter can be gradually added for Storm Cat or Halo without claiming an unobserved ancestor is absent.

# BRDB M6 / P1-4d — 2026 pre-day PACI × SED outcome cohort freeze (2026-11-04)

## Decision and scope

**PASS — research-only, SHA-pinned first fixed 2026 outcome cohort, 14 nominal race dates.**
**HOLD — predictive as-of acceptance, historical 2016–2025 as-of proof, prospective model evaluation, Blood Score, BRDB CURRENT/PWA/RaceNote publication.**

This is a separately scoped 2026 study and must never replace the 2016–2025 P0-2 research mart. The new input type is the 14 PACI ZIPs for which native Drive provider metadata indicated **both original creation and latest modification before 00:00 JST on the nominal race date**, plus their official SED *post-race* result files. The connected Drive revision listing returned one revision per accepted PACI. These facts demonstrate *Drive-side calendar-day storage*; there is still **no independently attested original JRDB distribution receipt or contemporaneous pre-race ZIP SHA**. `prediction_safe=false` remains mandatory.

## Sources, identity and executable contract

- 2026 input candidate: [BRDB P1-4c provider/UKC/KYI inventory](BRDB_M6_P1_4C_2026_PACI_PRE_DAY_AUDIT_20261104.md) — 14 days/4,945 PACI-KYI declarations, strictly pre-day Drive metadata.
- Source data resides in the existing approved JRDB `00_raw/PACI` and `00_raw/SED` folders, never in Git. Exactly 14 PACI ZIPs, 14 selected SED ZIPs and 3 SED duplicate/revision comparator ZIPs were SHA-256 and byte-size pinned in a **private manifest** (31 source ZIP files). Manifest SHA-256: `fb95159c87c879a24748b9150b2cfefe1bc53c2cc0379b71b82df95957505ad2`.
- Local private code input contract explicitly sets `prediction_safe=false`. A JSON-supplied provider timestamp is only a recorded assertion; the original independent Drive metadata discovery is documented in P1-4c. The code does **not cryptographically attest** a provider event or historical pre-race original contents.
- `src/audit_brdb_m6_2026_outcome_cohort.py` reuses **exact GitHub main** `jrdb_raw.Parser.kyi`, `Parser.sed`, `split_fixed_records`, and `jrdb_ukc.parse_ukc_record`. No new fixed-width byte parser is introduced.
- Primary identity is `(race_key_raw, horse_no, blood_registration_no)`, with duplicate-key rejection, full KYI ↔ SED key-set equality and ordered UKC ↔ KYI blood-registration-number equality. SED `date_raw`, UKC `data_date`, file membership, CRC, ZIP SHA/size, and PACI provider-metadata calendar-day limits are checked.
- Output private per-entry CSV contains race/horse keys, outcome code/finish, source SHA identities and normalized **actual-starter/normal-finisher** flags. This licensed row-level CSV must **not** enter GitHub. Only aggregated code/audit findings and synthetic tests are committed.

## Official JRDB status interpretation

Native Google Drive official specs `00_document/official_specs_20261015/Sed__sedsiyo_doc` define SED `abnormal_code`: `0` normal; `1` cancel; `2` exclude; `3` race stopped; `4` disqualification; `5` relegation; `6` remount. In this frozen cohort only `0/1/2/3` appear. **KYI declarations != actual starters != normal finishers.**

| Outcome evidence | Entries |
|---|---:|
| KYI declared entrants | **4,945** |
| SED matched on all 3 canonical key fields | **4,945** |
| Actual starters = declarations minus `1` and `2` | **4,932** |
| Normal finishers, code `0` | **4,919** |
| Cancelled, code `1` | 7 |
| Excluded, code `2` | 6 |
| Did not finish, code `3` | 13 |
| Code `4/5/6` | 0 |
| Races | **372** |
| Distinct horse IDs | **3,970** |
| Horses appearing on multiple declared entries | **906** |
| Additional entries caused by repeated horses | **975** |

### Per-day counts

| Date | KYI/SED matches | Actual starters | Normal finishers |
|---|---:|---:|---:|
| 2026-09-19 | 287 | 286 | 285 |
| 2026-09-20 | 334 | 334 | 333 |
| 2026-09-26 | 313 | 312 | 312 |
| 2026-09-27 | 307 | 306 | 304 |
| 2026-10-03 | 349 | 349 | 348 |
| 2026-10-04 | 362 | 361 | 361 |
| 2026-10-10 | 315 | 315 | 315 |
| 2026-10-11 | 344 | 344 | 344 |
| 2026-10-12 | 321 | 321 | 320 |
| 2026-10-17 | 472 | 471 | 470 |
| 2026-10-18 | 450 | 448 | 446 |
| 2026-10-24 | 468 | 466 | 464 |
| 2026-10-31 | 305 | 304 | 304 |
| 2026-11-01 | 318 | 315 | 313 |

## Duplicate SED verification (important result-source guard)

The canonical SED folder exposes duplicate same-name ZIPs on 2026-10-10, 10-11 and 10-12. The private manifest pins the **earlier Drive-file version** as selected and the **later version** as an independently checked comparator. No silent name-only selection is permitted.

- 2026-10-10: 315 rows match on identities, finish, abnormal code and date. 315 rows differ in at least one non-outcome field across the two versions.
- 2026-10-11: 344 rows match on identities, finish, abnormal code and date. 344 rows differ in non-outcome fields.
- 2026-10-12: selected and alternative ZIPs have identical full ZIP bytes, and outcome differences are 0.
- 2026-10-10 and 10-11 include post-race IDM/metrics amendments. **No IDM or any post-race derived field is imported as a pre-race feature.** Any future alternate that changes canonical identity, finish, abnormal code or result date fails closed.

## Reproducibility and acceptance

- Local original ZIP audit: **PASS, all 14 days, all 4,945 entries matched**, 0 source SHA/size/CRC/UKC-KYI identity problems.
- Synthetic-only regression: **4/4 PASS** locally and on pinned Github source via [Actions run 41775619858](https://github.com/yukki0113/GPT/actions/runs/41775619858), DuckDB 1.1.3 / PyArrow 25.0.1. Source-only GitHub export was executed from a **separate, unmerged temporary branch**, without publishing licensed rows.
- The initial test fixture [Issue #2381](https://github.com/yukki0113/GPT/issues/2381) failed on a Python `Path` grouping mistake, corrected and confirmed PASS with [Issue #2382](https://github.com/yukki0113/GPT/issues/2382). This failed attempt remains in the audit trail; acceptance relies only on the corrected run.
- Exact GitHub blobs checked against locally replayed source: `src/audit_brdb_m6_2026_outcome_cohort.py` blob `d1015ecf55f1d61281df9e0b4940a21968681555`, `tests/test_audit_brdb_m6_2026_outcome_cohort.py` blob `9a36e8beedf5e126ec33a16c890e3876d08626de`.
- Original private root and separately materialized alternate root were run with the **same exact GitHub-committed source**. Their full aggregate JSON and private 4,945-row CSV were **byte-for-byte identical**.
- Private aggregate JSON SHA-256: `0483eb80a7fdaf810beec5f726445d053610257528c7cca1b1e5bd040814b42c`.
- Private outcome CSV SHA-256: `86e78c096346a8fa79192afcf620e1dc12e895badd84a05b13b68c95a740749e`.
- The private ZIP/row-level outputs and manifest remain in the private analysis environment; this PR does not publish or assert a long-term Drive archival copy of those derived files. Source ZIPs remain in their original approved Drive folders.

## Reproduction in an authorized private runtime

```bash
python horse-racing/brdb/src/audit_brdb_m6_2026_outcome_cohort.py \
  --source-root <PRIVATE_MATERIALIZED_14_PACI_14_SED_AND_3_COMPARATOR_ZIPS> \
  --private-manifest <PRIVATE_SHA_PINNED_SOURCE_MANIFEST_JSON> \
  --out <PRIVATE_RESULT_DIR>

python -m unittest discover -s horse-racing/brdb/tests \
  -p 'test_audit_brdb_m6_2026_outcome_cohort.py' -v
```

## M6 stage-gate decision

- **P1-4d data preparation and result join:** PASS (research-only). We now have a rigorously outcome-labeled **2026 14-day candidate cohort**.
- **P1-5 dependence-aware predictive inference:** HOLD for *prediction claims*; same horse appears repeatedly, race-level dependence remains, and 14 days do not support multi-year generalization.
- **P1-6 multi-window walk-forward and P1-7 value over existing baselines:** HOLD; insufficient independent date span and no time-of-distribution-proof of original upstream UKC bytes.
- **2016–2025 as-of historical proof:** remains 0 independently proven rows; do not import these 2026 results into the retrospective P0-2 mart to bypass that boundary.
- **BRDB CURRENT, Blood Review v0.1, RaceNote, PWA, Newspaper, publishing and betting prediction:** unchanged.

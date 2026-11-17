# BRDB Stage3B held-root identity debt resolution — 2026-11-17

Status: **PASS — 5 HELD ROOT IDENTITIES RESOLVED FOR RESEARCH / 50 OF 50 ROOT DECISIONS APPROVED / HISTORICAL AS-OF STILL UNVERIFIED**

This closes only the five Stage3B **root identity** holds from the 2026-11-06 top50 re-audit. It does not resolve all ancestor-slot name differences, missing names, historical source timing, or predictive validity.

## 1. Fixed JRDB source re-audit

Canonical research generation:
- generation: `5279af0bd8226cde`
- approved Drive ZIP: `issue2223_research_generation_v02_5279af0bd8226cde_20261030.zip`
- ZIP SHA-256: `672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4`
- `pedigree_fact.parquet` SHA-256: `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536`

Read-only root audit:
- Issue [#2621](https://github.com/yukki0113/GPT/issues/2621)
- Actions run [44029015131](https://github.com/yukki0113/GPT/actions/runs/44029015131)
- status: **PASS**
- DuckDB 1.1.3 / PyArrow 25.0.1

The audit queried only the minimum root profile fields required for the five held subjects.

### Fixed JRDB facts

| root | JRDB ID | birth | sex | sire | dam | sire/dam birth year |
|---|---|---|---|---|---|---|
| リアルスティール | `12104889` | 2012-03-01 | 牡 | ディープインパクト | ラヴスオンリーミー | 2002 / 2006 |
| シンボリクリスエス | `99110099` | 1999-01-21 | 牡 | クリスエス | ティーケイ | 1977 / 1991 |
| モズアスコット | `14110031` | 2014-03-31 | 牡 | フランケル | インディア | 2008 / 2003 |
| タワーオブロンドン | `15101621` | 2015-02-09 | 牡 | レイヴンズパス | スノーパイン | 2005 / 2010 |
| ヘニーヒューズ | no JRDB root profile in this fixed generation | — | — | — | — | — |

The Henny Hughes discovery query used year=2003, male, sire-line=1108, sire=`Hennessy`, dam=`Meadow Flyer`; it returned zero JRDB root candidates. Therefore no JRDB ID is inferred.

## 2. Current primary-source evidence used only to resolve identity notation

Collected 2026-11-17. These pages are current source evidence and **do not establish historical pre-race availability**.

- Real Steel / JBIS `0001157711`: 2012-03-01, male, Deep Impact, Loves Only Me; JRA independently shows the same root profile.
- Symboli Kris S / JBIS `0000700008`: 1999-01-21, male, Kris S., Tee Kay; JRA independently shows the same root profile.
- Henny Hughes / JBIS `0001028940`: 2003-04-05, male, Hennessy / Meadow Flyer.
- Mozu Ascot / JBIS `0001213491`: 2014-03-31, male, Frankel / India; JRA race evidence independently shows the same root/birth/parents.
- Tower of London / JBIS `0001209439`: 2015-02-09, male, Raven's Pass / Snow Pine; JRA independently shows the same root profile.

The fixed evidence record is:
`taxonomy/stage3b_root_external_evidence_20261117.json`.

## 3. Explicit alias policy

No general transliteration or fuzzy matching was added.

`taxonomy/stage3b_root_parent_aliases_research_v0_1.json` contains exactly seven target+role-scoped pairs:

1. Real Steel dam: `ラヴスオンリーミー` ↔ `ラヴズオンリーミー`
2. Symboli Kris S sire: `クリスエス` ↔ `Kris S.`
3. Symboli Kris S dam: `ティーケイ` ↔ `Tee Kay`
4. Mozu Ascot sire: `フランケル` ↔ `Frankel`
5. Mozu Ascot dam: `インディア` ↔ `India`
6. Tower of London sire: `レイヴンズパス` ↔ `Raven's Pass`
7. Henny Hughes sire: `Hennessy` ↔ `ヘネシー`

Country suffixes such as `(USA)` / `(GB)` continue to be stripped by the already-established source comparison rule. No alias applies outside the exact target+parent-role pair.

## 4. Resolution decision

Four JRDB-bound roots require:
- root name match;
- full birth date match;
- male sex match;
- sire/dam birth-year match;
- sire/dam exact match after country suffix removal OR an explicit target+role alias.

Henny Hughes remains **JBIS source-only**:
- same JBIS ID as the pre-existing source seed;
- birth year and male sex match;
- sire/dam seed-vs-profile comparison passes only with the explicit Hennessy ↔ ヘネシー alias;
- `jrdb_horse_id=null` is mandatory.

Result:
- baseline approved: **45**
- newly resolved: **5**
- research root decisions approved: **50/50**
- inferred JRDB IDs added: **0**

Generated decision:
`taxonomy/stage3b_root_decisions_research_v0_2.json`

SHA-256:
`41af186f3d48e5357c835ace0fb0507fd9ec33a05c2747e82c3fcac984980740`

## 5. Real execution and byte verification

Resolution:
- Issue [#2622](https://github.com/yukki0113/GPT/issues/2622)
- Actions run [44029492107](https://github.com/yukki0113/GPT/actions/runs/44029492107)
- status: **PASS**
- source commit: `feeb343c8f4284b5e5c903c50b9dc3d610aee02e`

Independent committed-byte verification:
- Issue [#2623](https://github.com/yukki0113/GPT/issues/2623)
- Actions run [44029898216](https://github.com/yukki0113/GPT/actions/runs/44029898216)
- status: **PASS**
- source commit: `30f6157d2776c6aa1e830b8ad13c4faa1b2472a7`

The verifier regenerated v0.2 from the fixed root audit + frozen v0.1 decisions + source evidence + explicit aliases + pre-existing external seed, then required:
1. byte equality with the Git-tracked v0.2 decision; and
2. SHA equality with `41af186f...`.

Both passed.

## 6. What this closes — and what it does not

Closed:
- the five root-level `ROOT_IDENTITY_REVIEW_REQUIRED` holds;
- the former Real Steel profile-acquisition gap;
- exact source notation differences for the seven explicitly reviewed parent-role pairs.

Still open:
- **36 ancestor-slot label differences** from the 2026-11-06 top50 slot audit;
- **10 missing 2nd-generation names** and **40 missing 3rd-generation names**;
- old-ancestor person-ID coverage;
- any additional direct-parent edge certification not already accepted by Stage3C;
- historical race-day source availability for these current external pages;
- predictive interpretation.

All outputs remain:
- `research_only=true`
- `prediction_safe=false`
- `historical_asof_status=AS_OF_UNVERIFIED`

No BRDB CURRENT, Blood Review v0.1, RaceNote, PWA, Newspaper, score, factor or forecast contract is changed.

# BRDB condition and relatives discovery v0.3 candidate — 2026-11-19

Status: **research-only implementation; local real-field replay PASS; no publication or prediction authorization**.

## Why this increment

Keep the agreed architecture:

```text
PACI + private M7 evidence → BRDB common machine JSON
                                   ├→ v0.1/v0.2 descriptive discovery
                                   └→ v0.3 relatives/going condition sidecar
                                                 └→ separate editorial formatter (research only)
RaceNote forecast and Newspaper/PWA production consumers: NOT CONNECTED
```

The user wants actual nontrivial discoveries such as mud-condition observations, sire×BMS conditional differences, and maternal relatives supporting a distance discussion. This release establishes **input/data and reasoning boundaries**, *not* validated causal pedigree aptitude. We must not hallucinate review text when evidence is unavailable.

## Canonical sources and inputs

- `src/brdb_common_analysis_adapter.py` / `schema/brdb_common_analysis_v0_1_candidate.schema.json`: existing local research candidate, now proposed for repository. Consumes private M7 v0.3, detailed relatives, preview, exact Newspaper race. **No confidential horse JSON in Git.**
- `src/brdb_cross_discovery.py`: v0.2 parent discovery (PR #2655), same `(horse_no, canonical 8-digit horse_id)`, same race, exact as-of.
- `src/brdb_condition_discovery.py`: new sidecar; consumes `common`, v0.2 `cross`, private M7 detailed relatives, and optionally a **separate verified-normalization candidate** of past SED horse-start rows for going observations.
- `src/brdb_condition_editorial.py`: optional template formatter of **literal observed facts only**. No final review paragraph or betting Tips.
- `schema/brdb_condition_discovery_v0_3_candidate.schema.json`, `schema/brdb_going_observation_input_v0_1_candidate.schema.json`: candidate input/output shapes.

### Private read-only real replay

2026-11-15 東京12R `race_key=05265412`, 芝2000m, 18 entries. Actual unchanged personal Library `/BRDB/M7/`: integrated v0.3, detailed relatives, consumer preview, canonical Newspaper. Both `common` and `cross` were generated from the exact local private inputs. Full-cohort reconciliation passes; M7 detailed-relative raw-file SHA is checked against the common contract. **No personal/licensed horse-level payload in Git**.

- 18/18 horse identities match; 75 relatives, 375 five-scope cells, 285 zero-start cells (rate `null`).
- For the 75 relatives: 2 FULL_SIBLING, 23 MATERNAL_HALF_SIBLING, 50 MATERNAL_AUNT_UNCLE. Across the 375 cells, 90 have at least 1 start; the remaining 285 have 0.
- The prototype editorial formatter produces 11 per-scope *literal observation sentences* for the full field, not 11 verified pedigree suitability discoveries.
- Actual going per-start SED data were **not available in the replay**. Going remains `SOURCE_UNAVAILABLE` for all 18. Separate synthetic going-normalized rows verify shape/safety only.

## Semantics of relatives

- Preserve **each individual confirmed canonical relative horse ID**, exact relationship and five condition scopes from M7; NO inference of full sibling from name similarity.
- `SAME_DAM_SAME_SIRE_NAME_UNVERIFIED` is not normalized into `FULL_SIBLING`.
- Group per *relationship × scope*. `sum(starts)` is descriptive **starts for relatives** within that scope; does not establish independent horses or conditional superiority.
- The 5 scopes overlap; **never sum between scopes**. `NO_SAMPLE` stays 0 starts and `top3_rate: null`. Do not convert “no observed racing” to unfavorable aptitude.
- Historical pedigree join is `AS_OF_UNVERIFIED`, regardless of successful description of past starts. All fields and generated fact sentences remain unpublished and prediction-ineligible.

## Going observation interface, not a filled history

JRDB common Reader `horse-racing/jrdb/src/jrdb_raw.py::sed()` exposes `track_condition_code`. BAC (the PACI race basis) does **not** provide pre-race ground-condition forecasts. The existing BRDB sire/bms history query currently does not carry going.

The optional `--going` JSON input is **not** arbitrary per-race user prose. It must be created in a separately validated SED ingestion stage using the existing JRDB Reader, official track-condition code mapping, completion rules, canonical horse IDs, historical sire-link policy, source generation/SHA and `race_date < target_date`; do not invent the actual code-to-label mapping.

- `records[]`: historical race key, date, `(horse_no, horse_id)`, surface, verified `going_class` (良/稍重/重/不良), verified historical sire label, `outcome` and finish.
- Enforce no future date, cross-surface mixing, duplicate historical start, invalid going, nonfinish exclusion, malformed horse ID, and source research flag.
- Output counts currently aggregate **all distances in the same surface**, split by going class. This is a preliminary context, **not suitable to declare target-distance/venue going aptitude**; target distance/venue breakdown and comparable-rate controls are next. If no audited input: `SOURCE_UNAVAILABLE`, never silently assume 良.
- `--target-going 良|稍重|重|不良`: independent user-supplied *assumption* for target race; omitted = `NOT_SPECIFIED`. This is not PACI-extracted and never promotes historical statistics to prediction.
- Note: current `historical_parent_mapping_status` is a source assertion. Before operational use, validate it from the canonical join/replay and the immutable history manifests, not a self-declared JSON flag.

## Output and wording boundary

**BRDB analysis JSON** v0.3 contains only structured evidence: individual relative IDs, grouped condition counts, going counts/availability, assumed target going, provenance, nulls, pending reasons and explicit publication prohibitions. It contains **no reviews or betting Tips**.

Separate `brdb_condition_editorial.py` builds research candidate *observation sentences* from evidence only, e.g. “母方近親（MATERNAL_HALF_SIBLING）は同芝ダート・同距離で4走中2回が3着以内。血統関係の過去時点での完全再現は未検証。” It deliberately returns `review_paragraph: null`, `betting_tips: []`, `display_authorized: false`. Even the fact sentences are **not yet PWA text**, because the historic-as-of guarantee is not accepted.

Qualifiers: `LOW_SAMPLE` remains observed; high rate at low N can be mentioned with N, but not implied future aptitude. Country roots, offspring inheritance of dam-side distance aptitude, mud suitability, and betting signals are **NOT validated**.

## Commands

```bash
python src/brdb_condition_discovery.py \
  --common /private/common.json \
  --detail /private/m7_relatives_detail_candidate.json \
  --cross /private/cross.json \
  --output /private/condition.json \
  --target-going 稍重
# Optional --going /private/audited_sed_normalized_going.json

python src/brdb_condition_editorial.py \
  --input /private/condition.json --output /private/observation_text.json

python -m unittest discover -s tests -p 'test_brdb_condition_*.py' -v
```

## Required next verification gates

1. Integrate real historical SED track-condition values into an **audited** normalized going input using the existing Reader, official mapping and immutable manifest. Test a real date with history; no input means no going judgment.
2. Add same-distance and same-venue/surface stratification, sample sizes and appropriate comparison baselines; do not compare all-distances going to target-distance suitability.
3. Validate historical parent relation as-of across M7, stronger relation provenance, and whether observed reference group contains the entered horse or other overlaps.
4. Only after those checks, implement a finding selector and separately reviewed, evidence-ID-cited total review/Tips; then real device PWA and RaceNote approval gates (M6-P separate).
5. New sidecar and common contract are *candidate*. No release, `CURRENT`, RaceNote, predictions, marks or PWA change. The current PR remains Draft pending CI and scientific acceptance.

# RaceNote Pedigree Enrichment Design v0.1

Status: **FEASIBILITY CONFIRMED / IMPLEMENTATION NOT YET CUT OVER**
Date: 2026-09-29

## 1. Background

CAL-001 under `RaceNote-Human-Context-Reader-0.3` exposed repeated information gaps:

- newcomer / inexperienced horses: pedigree-derived distance suitability
- sibling debut / middle-distance tendencies

Obstacle-specific evidence is explicitly out of scope for this design.

The purpose of this document is to separate pedigree information that is
already available from information that requires a new canonical source.

## 2. Confirmed existing data

### 2.1 PACI / KYI identity

JRDB KYI contains:

- `blood_registration_no`
- horse name

The common parser already preserves:

`horse-racing/jrdb/src/jrdb_raw.py`

- `blood_registration_no`

RaceNote identity already uses this value as `horse_id`.

### 2.2 Existing project pre-race outputs

Existing JRDB Newspaper/current-entry packages already expose, under
per-horse `basic`:

- `sire_name`
- `dam_name`
- `broodmare_sire_name`

These are pre-race identity facts and are already present in operational
project artifacts.

### 2.3 Analysis canonical

Analysis v1.4 fact schema contains:

- `horse_id`
- `horse_name`
- `sire_name`
- `broodmare_sire_name`
- `sire_line_code`
- `broodmare_sire_line_code`

Analysis already supports sire population context used by RaceNote Trend /
population context.

Important: Analysis is a post-race fact store. It must not become an
unrestricted pre-Freeze source merely because pedigree fields are immutable.

## 3. Recommended scope

### Phase P1 — Horse pedigree identity

Add a non-scoring pedigree block to each RaceNote horse:

```json
"pedigree": {
  "sire_name": "...",
  "dam_name": "...",
  "broodmare_sire_name": "...",
  "sire_line_code": "...",
  "broodmare_sire_line_code": "...",
  "source": "...",
  "source_as_of": "...",
  "coverage_status": "FULL|PARTIAL|NONE"
}
```

Minimum P1 fields:

- sire_name
- dam_name
- broodmare_sire_name

Line codes are optional but useful because Edge / historical research already
uses them.

No pedigree score or suitability label is created in P1.

### Phase P2 — Pedigree historical context

Build non-scoring historical context from as-of-safe historical data.

Candidate context:

- sire × surface
- sire × surface × distance / distance band
- sire × venue × surface × distance where available
- broodmare sire × surface
- broodmare sire × surface × distance / distance band

Output must preserve:

- starts
- finish record / win-top3 counts
- win / top3 rate
- sample size
- as-of-exclusive date
- source / generation

Small samples remain visible and are not discarded solely for being small.

P2 is context, not a deterministic recommendation.
Do not convert it into one aggregate pedigree suitability score.

## 4. Source policy

Preferred order:

1. existing pre-race current-entry pedigree source already used by operational
   Newspaper/current facts;
2. a dedicated immutable pedigree master keyed by JRDB blood registration no;
3. Analysis only through a dedicated pedigree-only safe projection if required.

Do not let Forecast / RaceNote read arbitrary Analysis post-race rows pre-Freeze.

If Analysis fallback is implemented, the adapter must expose only approved
immutable identity fields and must fail closed on unexpected columns.

## 5. Historical backtest / firewall

Pedigree identity is immutable, but source provenance still matters.

For historical replay:

- target results remain forbidden;
- current/future result fields must not become readable through the pedigree path;
- a pedigree-only projection may use horse identity but must not expose finish,
  payout, final odds, popularity, post-race review, or result-derived features;
- provenance must state source generation and projected field whitelist.

## 6. Siblings / family performance

CAL-001 requested:

- sibling debut tendencies
- sibling middle-distance performance

This is **not covered by P1/P2**.

Why:

- current Analysis v1.4 does not provide `dam_name` as a canonical fact column;
- sibling relation requires a stable maternal identity key or equivalent horse
  master;
- matching only by free-text dam name across ad-hoc artifacts is not sufficient
  for a canonical RaceNote feature.

Separate investigation required:

1. locate an authoritative/current pedigree master with maternal identity;
2. define sibling relation (same dam; half-siblings through sire are not the
   intended relation);
3. build historical child-race aggregation with strict `race_date < target_date`;
4. distinguish:
   - sibling debut performance
   - sibling same-surface performance
   - sibling distance-band performance
   - sibling class/age context
5. keep sample count visible; do not infer suitability from one sibling without
   showing the underlying record.

Until such a source is canonical, RaceNote should report sibling evidence as
unavailable rather than infer it.

## 7. Newcomer use

For newcomer races, P1/P2 would materially improve the current RaceNote because
the Forecast can compare:

- training / stable readiness
- sire distance/surface context
- broodmare-sire distance/surface context

without inventing an ability rank from nonexistent race history.

This directly addresses part of the CAL-001 information gap.

Sibling evidence remains a later enhancement.

## 8. Non-goals

- no obstacle-specific pedigree logic in this phase
- no fixed pedigree weight
- no pedigree-only ◎ selection
- no market/odds use
- no result leakage
- no auto-generated "distance suitable" label from raw percentages
- no deletion/replacement of existing Trend evidence

## 9. Proposed implementation order

1. Confirm exact current-entry source used for
   `sire_name / dam_name / broodmare_sire_name`.
2. Add pedigree fields to the authoritative RaceNote horse schema.
3. Preserve them losslessly in Reader View.
4. Add schema/round-trip/firewall tests.
5. Add P2 sire + broodmare-sire historical context using existing Analysis /
   Trend machinery.
6. Run a small 3–5 race calibration focused on newcomer / lightly raced horses.
7. Only after P1/P2 is stable, investigate maternal sibling history.

## 10. Acceptance criteria

P1 PASS when:

- every horse with upstream pedigree data exposes it unchanged;
- missing pedigree stays null / coverage-marked, never guessed;
- semantic round-trip remains PASS;
- no post-race field becomes visible;
- existing RaceNote source hash / provenance contract remains auditable.

P2 PASS when:

- all historical rows satisfy `race_date < target_date`;
- sire and broodmare-sire contexts expose sample sizes;
- no aggregate pedigree score is emitted;
- small-n contexts remain visible;
- Forecast can cite the pedigree context as one evidence lane among others.

## 11. Current recommendation

Proceed with P1 first, then P2.

Do not block P1/P2 on sibling support.

Sibling support should be a separate source/research task because its canonical
maternal identity path is not yet confirmed.

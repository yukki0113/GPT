# RaceNote Forecast Human-Context Reader v0.4.4 Candidate

Status: **PROSPECTIVE BTDAY CANDIDATE — NOT YET PROMOTED TO PRODUCTION**  
Date: 2026-10-03  
Candidate logic id: `RaceNote-Human-Context-Reader-0.4.4-candidate`  
Fixed historical baseline: `RaceNote-Human-Context-Reader-0.4.2-candidate` on BTDAY-0023–0032  
Completed predecessor prospective cohort: `RaceNote-Human-Context-Reader-0.4.3-candidate` on BTDAY-0036, 0037, 0040, 0041  
RRDB recommendation contract: `rrdb-recommendation-signals-v0.3`

## 1. Purpose

v0.4.4 is a bounded refinement of v0.4.3.

It preserves the v0.4.3 hierarchy and independent ▲ semantics. The only
intended logic change is to make the support-boundary Coverage review explicit,
mandatory and auditable.

v0.4.4 does **not** introduce:

- a score or fixed weight;
- a threshold table;
- a matched-signal count;
- popularity or odds;
- a sixth selected horse;
- automatic RRDB promotion;
- automatic ▲ promotion;
- broad outsider hunting;
- forced Coverage swaps.

The five marks remain ◎ ○ ▲ △1 △2.

## 2. Research basis

The v0.4.3 formal prospective cohort is fixed at 132 clean-blind races:

- BTDAY-0036: 36R
- BTDAY-0037: 36R
- BTDAY-0040: 24R
- BTDAY-0041: 36R

Across those 132 races every recorded v0.4.3 consistency pass remained
unchanged. In particular, Coverage always recorded no challenger.

BTDAY-0041 supplied a useful stress case. Retrospective semantic review of its
16 unmarked winners classified:

- SWAP_CANDIDATE: 6 / 16
- COMPLETE_MISS: 6 / 16
- AMBIGUOUS: 4 / 16

This does not justify broadening the five-horse net. It does show that a
generic `coverage_challenger = null` is not sufficient evidence that the
support boundary was actually compared.

Therefore v0.4.4 changes **observability and execution of the narrow Coverage
check**, not its conservative decision standard.

## 3. Inherited v0.4.3 contract

Unless this document explicitly changes a point, v0.4.3 is inherited.

In particular:

- read the whole race before assigning marks;
- integrate pre-Freeze evidence flexibly rather than with fixed scoring;
- current target-day market information is unavailable and must not be inferred;
- RRDB is reinterpretation evidence, not an additive vote;
- ▲ remains an independently selected single-shot / 単穴 role;
- the hierarchy consistency pass remains semantic;
- the conservative ▲ promotion gate remains unchanged;
- reader-facing prose remains governed by
  `FORECAST_READER_FACING_PROSE_v0_1.md`.

## 4. v0.4.4 reasoning flow

Conceptually:

```text
read the whole race
  -> build ordinary mainline contenders
  -> independently identify the best single-shot / ▲ case
  -> provisional ◎ ○ ▲ △1 △2
  -> HIERARCHY CONSISTENCY PASS
  -> ▲ PROMOTION GATE
  -> EXPLICIT COVERAGE SCAN
  -> identify BEST UNMARKED CHALLENGER or prove none eligible
  -> compare provisional △2 vs challenger
  -> KEEP / SWAP / NO_ELIGIBLE_CHALLENGER
  -> final five unique marks
  -> reader-facing explanation
  -> Freeze
```

The Coverage scan is a boundary verification step. It is not a second full
ranking pass.

## 5. Hierarchy consistency pass

Inherit v0.4.3 unchanged.

After provisional marks exist, compare ◎ primarily against ○ and, when
relevant, △1 / △2.

Review:

1. consistency with the authored `race_model`;
2. material direct-condition evidence;
3. "runs well" evidence versus a concrete "can win" route;
4. visible finish versus transferable hidden time/load/pace content.

Do not promote from one isolated field or label.

## 6. ▲ promotion gate

Inherit v0.4.3 unchanged.

▲ is not ordinary rank 3. Keep it independent unless its pre-Freeze evidence
has become mainline-grade rather than merely conditional asymmetric upside.

Coverage must never remove or repurpose ▲ to make room.

## 7. Explicit Coverage Scan

### 7.1 Purpose

After provisional △1 / △2 exist, perform one bounded scan of the **unmarked
horses** solely to test the support boundary.

Do not fully rerank the field.

### 7.2 Lightweight unmarked scan

For each unmarked horse, check only whether there is meaningful evidence
transferable to today's:

- course;
- distance;
- surface;
- class;
- race shape / expected position;
- recent directly relevant performance.

The scan must leave an audit summary containing:

- `unmarked_count`;
- `direct_condition_candidate_count`;
- `shortlisted_horse_nos`.

This is audit metadata, not a score.

### 7.3 Best challenger

After the scan, identify exactly one best unmarked challenger when an eligible
challenger exists.

A challenger should normally satisfy both:

1. meaningful direct-condition evidence for today's race; and
2. no material general-ability gap versus provisional △2.

Supporting evidence may include hidden strength, prior trouble, training
improvement, Trend or RRDB reinterpretation. Supporting evidence alone is not
enough.

If no horse reaches the comparison boundary, set
`coverage_best_challenger = null` and use
`coverage_verdict = NO_ELIGIBLE_CHALLENGER`.

Do not use null as a generic shortcut.

## 8. Mandatory △2 boundary comparison

When a best challenger exists, compare it directly with the **provisional △2**
using four semantic dimensions:

1. direct-condition evidence;
2. general ability / class proximity;
3. today's race-model fit;
4. supporting evidence.

No numeric points are assigned.

Allowed comparison labels for the first three dimensions are:

- `CHALLENGER_STRONGER`
- `DELTA2_STRONGER`
- `ROUGHLY_EQUAL`
- `UNCLEAR`

The provisional △2 identity must remain in the audit even if a SWAP occurs.

## 9. Coverage verdict

### KEEP

Use KEEP when a challenger exists but does not materially beat provisional △2
at the support boundary.

Ambiguous cases default to KEEP.

### SWAP

Use SWAP only when all of the following are true in context:

- the challenger has materially stronger direct-condition evidence;
- there is no material ability gap against provisional △2;
- the evidence transfers naturally to the authored race model.

A SWAP replaces only provisional △2. The final five still contain exactly five
unique horses.

### NO_ELIGIBLE_CHALLENGER

Use this only when the explicit scan finds no horse worthy of a direct △2
comparison.

## 10. Boundary isolation

Coverage normally acts only on:

```text
best unmarked challenger <-> provisional △2
```

It must not move ◎, ○, ▲ or △1.

If the Coverage scan reveals evidence that appears genuinely mainline-grade,
do not promote mechanically through the Coverage step. Record the exceptional
fact in the reason and re-check the hierarchy semantically before Freeze.

## 11. Required audit trace

v0.4.4 requires:

```json
{
  "consistency_pass": {
    "hierarchy_reviewed": true,
    "hierarchy_changed": false,
    "hierarchy_reason": "...",

    "single_shot_promotion_reviewed": true,
    "single_shot_promoted": false,
    "single_shot_promotion_reason": "...",

    "coverage_scan_reviewed": true,
    "coverage_scan": {
      "unmarked_count": 11,
      "direct_condition_candidate_count": 3,
      "shortlisted_horse_nos": [13, 7, 11]
    },

    "coverage_best_challenger": {
      "horse_no": 13,
      "horse_name": "Example"
    },

    "coverage_challenger_case": {
      "direct_condition": "...",
      "ability_proximity": "...",
      "race_model_fit": "...",
      "supporting_evidence": "..."
    },

    "coverage_boundary": {
      "current_delta2": {
        "horse_no": 16,
        "horse_name": "Example Delta2"
      },
      "direct_condition_comparison": "CHALLENGER_STRONGER",
      "ability_comparison": "ROUGHLY_EQUAL",
      "race_model_comparison": "CHALLENGER_STRONGER"
    },

    "coverage_verdict": "SWAP",
    "coverage_changed": true,
    "coverage_reason": "...",
    "change_attribution": "COVERAGE_CHALLENGER"
  }
}
```

When there is no eligible challenger, `coverage_best_challenger` and
`coverage_challenger_case` are null, but the scan summary, provisional △2,
`NO_ELIGIBLE_CHALLENGER` verdict and concrete reason remain required.

## 12. Validator invariants

For v0.4.4, Validator must fail closed unless:

- hierarchy and ▲ passes were reviewed;
- Coverage scan was reviewed;
- scan counts and shortlist exist;
- provisional △2 is recorded;
- verdict is one of KEEP / SWAP / NO_ELIGIBLE_CHALLENGER;
- Coverage reason is non-empty;
- challenger identity is present for KEEP / SWAP;
- challenger is included in the shortlist;
- SWAP implies `coverage_changed = true`;
- KEEP / NO_ELIGIBLE imply `coverage_changed = false`;
- SWAP final △2 equals the challenger;
- KEEP / NO_ELIGIBLE final △2 equals provisional △2;
- NO_ELIGIBLE has no challenger;
- change attribution matches actual changes.

The schema and Validator provide observability. They do not select horses.

## 13. Market / result firewall

v0.4.4 retains the v0.4.3 clean input-binding requirement.

Before authoring:

- bind an immutable target-market-stripped Reader;
- expose only that Reader to the model;
- do not open target results;
- do not reopen the lossless market-bearing Reader during the Coverage scan.

Coverage is performed from the same accepted market-blind input used for the
rest of the forecast.

## 14. Reader-facing prose

No prose-contract change.

The short newspaper comment is still centered on ◎, concise on ○ and concrete
on ▲. △ boundary audit details remain internal unless genuinely useful to the
race-level explanation.

## 15. Prospective validation

The v0.4.3 formal prospective cohort is frozen at 132R and must not be
retroactively rewritten.

New unused BTDAYs after v0.4.4 activation are authored with v0.4.4 alone.
Do not create same-day v0.4.3 or v0.4.2 forecasts.

Compare:

```text
v0.4.2 fixed baseline: 336R
v0.4.3 completed prospective cohort: 132R
v0.4.4 new prospective cohort: accumulate on unused clean-blind BTDAYs
```

In addition to the existing outcome and ROI measures, report:

- eligible-challenger rate;
- KEEP rate;
- SWAP rate;
- NO_ELIGIBLE_CHALLENGER rate;
- Top3 gained by swaps;
- Top3 lost by removing provisional △2;
- net Coverage gain;
- winner-in-five and all-Top3-in-five;
- ▲ role integrity.

## 16. Summary

```text
v0.4.3
  + mandatory bounded unmarked scan
  + explicit best-challenger identity
  + mandatory challenger-vs-provisional-△2 comparison
  + KEEP / SWAP / NO_ELIGIBLE verdict
  + fail-closed auditable Coverage trace
  = v0.4.4 candidate
```

No score.
No fixed weight.
No automatic RRDB promotion.
No popularity rule.
No sixth horse.
No automatic ▲ promotion.
No broad outsider hunting.
No forced Coverage swap.
Market blind remains mandatory.

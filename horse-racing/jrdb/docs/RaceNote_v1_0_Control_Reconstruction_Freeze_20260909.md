# RaceNote v1.0 Control Reconstruction Freeze — 2026-09-09

Status: **PRE-HJC IMPLEMENTATION FREEZE**

This addendum resolves implementation details that are under-specified in `RaceNote_v0_2_Tested_Implementation_Spec_144R.md` for the first 2026 Edge-aware blind block. It is fixed before target HJC/SED/result acquisition.

It does not claim byte-for-byte identity with the historical ad-hoc 2025 harness. The control name for this experiment is:

```text
v0.2-reconstructed-20260909-a
```

The intent is a deterministic, documented-spec-compatible reconstruction.

## 1. Normalized ordinal ranks

For race field size `N`:

```text
normalized_rank = (average_tie_rank - 1) / (N - 1)
```

Higher-is-better raw features are ranked descending; lower-is-better features ascending. Missing values receive the median rank among available observations. If every observation is missing, use neutral `0.5`.

## 2. AbilityGood

Unchanged conceptually:

- current IDM rank
- current total_index rank
- mean recent-run IDM from up to latest 3 detailed runs

```text
AbilityGood = 1 - mean(three normalized ranks)
```

## 3. FrameFit

Use target `race_trends.frame[frame_no]` top3 rate.

Shrink toward 33% with:

```text
w = starts / (starts + 20)
shrunk = w * top3_rate + (1-w) * 0.33
FrameFit = clamp(shrunk / 0.45, 0, 1)
```

Missing frame evidence -> `0.5`.

This makes the previously documented “45% strong reference” and sample shrink deterministic for this reconstruction.

## 4. PaceStyleFit

Use the exact adjustments documented in `RaceNote_v0_2_Tested_Implementation_Spec_144R.md`, including:

- High: 逃げ -0.18 / 先行 -0.05 / 差し +0.15 / 追込 +0.10
- Slow: 逃げ +0.22 / 先行 +0.14 / 差し -0.08 / 追込 -0.18
- Average/other: 逃げ +0.08 / 先行 +0.08 / 差し +0.02 / 追込 -0.05
- deep 差し/追込 mid-position >70% field: -0.10
- position rank <=3: +0.08
- position rank >= max(8, field_size-2): -0.08

Base `0.5`, clamp `[0,1]`.

## 5. DistanceFit

Direct/nearby top3 quality uses:

```text
w = starts / (starts + 5)
shrunk = w * top3_rate + (1-w) * 0.33
```

Evidence order:

1. same_distance with starts >0;
2. first source-order distance range containing target distance with starts >0;
3. nearest source-order range whose boundary is within 400m, multiplied by `0.85`;
4. categorical distance_fit compatibility;
5. unknown -> `0.5`.

Categorical compatibility remains exact 1.00 / adjacent .55 / two buckets .20 / three buckets .05 / 万能 .90 / unknown .50.

If categorical compatibility <=.20 and same-distance starts=0, apply the documented final `-0.08` contradiction penalty.

## 6. SurfaceFit

Target surface mark:

- ◎ 1.00
- ○ .75
- △ .35
- missing/other .50

## 7. TimeFit

Among detailed `recent_runs`, search exact same venue + surface + distance and use each horse's fastest raw `time_sec`.

- fewer than 3 horses with comparable times -> all neutral `.5`;
- otherwise use lower-is-better normalized ordinal rank;
- a horse without an exact comparable time remains neutral `.5`.

No going/class/weight/pace/track-speed normalization is added.

## 8. Condition

Use the RaceNote v1.0 training-analysis indices because both are already on a 0-100 presentation scale:

- `training.analysis.training_index`
- `training.analysis.condition_index`

Scale each by `/100`, clamp `[0,1]`, average available values. Both missing -> `.5`.

Then apply training-arrow adjustment:

- デキ抜群 +.12
- 上昇 +.07
- 平行線 0
- やや下降気味 -.08

Final Condition is clamped `[0,1]`.

This choice is fixed before target settlement.

## 9. ForecastGood

Use forecast finish-order as lower-is-better normalized ordinal rank:

```text
ForecastGood = 1 - normalized_rank
```

## 10. Final control

```text
SuitabilityGood = .18*FrameFit + .25*PaceStyleFit + .30*DistanceFit + .12*SurfaceFit + .15*TimeFit
Good = .42*AbilityGood + .38*SuitabilityGood + .10*Condition + .10*ForecastGood
```

Then apply:

- distance contradiction `Good -= .08`
- Ability rank outside upper 60% `Good -= .05`

Sort descending Good; horse number is deterministic final tie-break. Top five are the v0.2 reconstructed control membership.

## 11. Confidence metadata

Confidence is not a primary endpoint in this Edge test. Because the historical confidence renderer is not fully specified numerically, this reconstruction uses a fixed metadata-only rule and does not use confidence for marks/tickets:

- C: P1-P2 Good gap < .015 or P1 has explicit distance contradiction
- A: gap >= .040, P1 AbilityGood >= .60, P1 SuitabilityGood >= .55, no contradiction
- B: otherwise

This label must not be used to reinterpret the primary result.

## 12. Edge layer

`v1.0-R` / `v1.0-V` logic is exactly the preregistered `RaceNote_v1_0_EdgeAware_Prediction_Design_Candidate.md`; no constants are changed here.

## 13. Blind boundary

At creation of this addendum:

- target dates are 2026-08-09 / 08-15 / 08-22;
- target HJC/SED/result/final odds/final popularity have not been acquired for this experiment;
- Edge Registry remains Issue #572 / run `34299375131` / ACTIVE SHA `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`;
- 2026-09-05/06 Edge Smoke outcomes are not part of this target block.

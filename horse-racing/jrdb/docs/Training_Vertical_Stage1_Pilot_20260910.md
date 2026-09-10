# Training Vertical Stage 1 Pilot — 2026-09-10

## Status

**PILOT SCREEN: CONTINUE / NOT A FROZEN EDGE MODEL**

This note records the first bounded pilot for the new training-edge research direction.
It does not define or promote a production index.

The question is deliberately narrower than general workout quality:

> When the selected main workout is unusually fast **for the same horse**, under a comparable workout course and furlong count, does the horse tend to outperform its own normal race-result level?

## 1. Scope and chronology

To keep the first pass small and avoid a full-history rebuild:

- result/history source: Analysis Lite v1.2, only rows with `year BETWEEN 2016 AND 2023`;
- CHA source: annual Raw `CHA_2017.zip` through `CHA_2023.zip`;
- 2016 result rows: performance-history formation only;
- 2017: performance + workout-history formation;
- 2018-2023: pilot evaluation;
- 2024-2025: **not loaded for outcome analysis and not inspected**.

No odds/popularity field is used.

The Common JRDB Reader remains the byte-position authority. No new CHA parser contract is introduced by this pilot.

## 2. Stage 1 pilot feature

Primary workout value:

- CHA selected main-workout final segment time (`final_segment_sec`).

Comparable historical group:

```text
same horse_id
+ same CHA course_code
+ same furlong_count
+ strictly earlier target race date
```

For current final-segment time `x`, with `n` prior comparable workouts:

```text
final_self_pct = (
    count(prior_time > x)
    + 0.5 * count(prior_time == x)
) / n
```

Interpretation:

- `1.0` = fastest end of the horse's own comparable history;
- `0.0` = slowest end;
- higher is better/faster.

Additional transparent deltas:

```text
final_delta_median_sec = prior_median_final_sec - current_final_sec
final_delta_prev_sec   = prior_previous_final_sec - current_final_sec
```

Positive values mean the current workout is faster.

## 3. Pilot outcome proxy

Analysis Lite does not contain Official RunPerf. Downloading/rebuilding the full Official RunPerf chain was intentionally avoided for this bounded screen.

Therefore the pilot uses only a coarse within-horse result proxy:

```text
finish_pct = (valid_finishers - finish) / (valid_finishers - 1)

performance_delta_proxy =
    current_finish_pct
    - median(prior valid finish_pct for the same horse)
```

Only normal positive finishes are used. Historical performance rows are strictly earlier by race date.

This proxy does **not** fully adjust race class, distance, surface or opponent strength. Consequently this pilot may decide whether the hypothesis is worth pursuing, but it must not freeze an Edge formula. A later confirmation should use Official RunPerf or another frozen ability-adjusted target.

## 4. Input integrity observations

CHA 2017-2023 contained 336,632 parsed rows before deduplication.

- malformed annual CHA body length: 0;
- exact duplicated CHA rows: 146;
- non-identical duplicate `race_key + horse_no` after exact deduplication: 0;
- CHA rows after exact deduplication: 336,486;
- CHA -> Analysis Lite join by `race_key + horse_no`: 100%;
- usable joined rows with horse identity, course, furlong count and final time: 323,433.

The 146 duplicates were exact record duplicates under the same race-horse key (for example records repeated across adjacent daily CHA members), so the pilot removes exact duplicates before any history calculation.

## 5. Evaluation population

Required for the main pilot population:

- target year 2018-2023;
- valid current result proxy;
- at least 3 prior valid race results for the horse;
- at least 3 prior comparable CHA workouts for the horse.

Result:

```text
evaluation rows : 115,288
unique horses   : 18,319
median prior comparable workouts : 6
median prior valid results       : 12
```

## 6. Main result

Fixed own-history workout quintiles produced:

| own-workout band | n | mean performance delta proxy | positive-delta rate | mean current finish percentile |
|---|---:|---:|---:|---:|
| slowest 20% | 25,512 | -0.11701 | 37.378% | 0.51140 |
| 20-40% | 19,633 | -0.11178 | 38.344% | 0.52071 |
| 40-60% | 17,437 | -0.11444 | 38.189% | 0.52801 |
| 60-80% | 21,642 | -0.10873 | 38.800% | 0.53117 |
| fastest 20% | 31,064 | -0.10079 | 40.294% | 0.54040 |

Fastest-20% minus slowest-20%:

```text
mean performance-delta difference : +0.01622
positive-delta-rate difference     : +2.92 percentage points (approximately)
```

Overall rank association is small:

```text
Spearman(final_self_pct, performance_delta_proxy) = 0.02246
```

So the pilot does **not** support a claim that own-history final-segment rank is a strong standalone predictor.

## 7. History-depth sensitivity

Using the transparent threshold comparison `final_self_pct >= 0.8` versus `<= 0.2`:

| minimum prior comparable workouts | evaluation n | high-low mean delta | high-low positive-rate difference |
|---:|---:|---:|---:|
| 2 | 136,264 | +0.01382 | +2.50 pt |
| 3 | 115,288 | +0.01632 | +2.91 pt |
| 4 | 93,853 | +0.01767 | +2.97 pt |
| 5 | 77,423 | +0.01812 | +3.12 pt |
| 6 | 64,398 | +0.02026 | +3.46 pt |
| 8 | 45,097 | +0.01808 | +3.14 pt |
| 10 | 31,758 | +0.01935 | +3.17 pt |

The effect does not disappear when more horse-specific workout history is required; it becomes slightly larger up to the 6-history threshold and then remains similar.

## 8. Near-personal-best sensitivity

Compared with the middle own-history band (`0.4 <= final_self_pct <= 0.6`):

| threshold | rows | mean performance-delta advantage | positive-rate advantage |
|---|---:|---:|---:|
| `final_self_pct >= 0.80` | 33,010 | +0.01204 | +1.79 pt |
| `final_self_pct >= 0.90` | 22,054 | +0.01648 | +2.43 pt |
| `final_self_pct >= 0.95` | 17,739 | +0.02030 | +2.83 pt |

This is compatible with, but does not prove, a weak 'near personal best' effect.

## 9. Same-horse paired check

To reduce stable horse-quality differences further, horses that experienced both:

```text
high state: final_self_pct >= 0.8
low state : final_self_pct <= 0.2
```

were compared within horse.

```text
paired horses                    : 8,389
mean(high - low performance delta): +0.01594
median difference                : +0.01373
share with positive difference   : 52.06%
```

This again points in the same overall direction, but the horse-level distribution is wide.

## 10. Annual stability

The simple fastest-quintile minus slowest-quintile mean performance-delta difference was:

| year | difference |
|---:|---:|
| 2018 | +0.02132 |
| 2019 | +0.01967 |
| 2020 | +0.02812 |
| 2021 | +0.00218 |
| 2022 | +0.01232 |
| 2023 | +0.02130 |

The aggregate sign is positive in every year, but 2021 is nearly flat.

A stricter year-local same-horse high-vs-low pairing was negative in 2021 (`-0.01442`) while the other years were positive. Therefore annual stability is not strong enough for a frozen Edge rule.

## 11. Controller interpretation

The first hypothesis is **not rejected**, but the signal is small.

Current interpretation:

1. Same-horse / same-course / same-furlong final-segment improvement contains a weak but repeatedly positive association with next-race over/under-performance proxy.
2. Requiring deeper comparable workout history does not remove the association.
3. Near-personal-best states show somewhat larger differences than middle states.
4. The effect is far too small and too proxy-dependent to become a standalone index or a buy rule.
5. The 2021 instability and the coarse finish-percentile target require a stronger confirmation stage.

Disposition:

```text
STAGE1_PILOT = CONTINUE
PRODUCTION_EDGE = NOT_AUTHORIZED
FORMULA_FROZEN = false
2024_2025_OUTCOMES_INSPECTED = false
```

## 12. Recommended next gate

Do not broaden immediately into trainer-pattern mining or JRDB's final workout/finish ratings.

The next useful step is Stage 1b:

- retain the same transparent workout feature definition;
- use Official RunPerf (or the existing frozen ability-adjusted target) as the outcome;
- keep development through 2023 only;
- compare `final_self_pct`, median delta and previous-comparable delta;
- separately test CHA JRDB final-segment index vertical comparison as a normalization challenger;
- check surface/distance/class and layoff strata only after the primary result is reproduced;
- keep 2024-2025 outcome metrics unopened until a Training Edge definition is frozen.

# RaceNote v1.1-P Polarity-Gated Blind Result — 2026-07-04 / 07-25 / 07-26

Status: **SETTLED / REPEAT_UNCHANGED**

## Blind boundary

- target races: 108
- prediction freeze commit: `4aef9a0749f74a35837063ac2805c9ed44f081b5`
- freeze manifest SHA-256: `6ec6dcedcd8b422395118b82af42e726d5c4bfbd11c9090298bc9dd4766089e1`
- frozen combined canonical payload SHA-256: `be90119c73ce557365b8db39f5194c7be6ecba6d160876798f1f99e96d3262c7`
- result data used at prediction freeze: `false`
- settlement Issue: `#767`
- settlement run: `34420257178`
- settlement commit: `555cfbc21aea6a9fede971efdea55c4d5d0c7005`
- metrics SHA-256: `5f49d53ff7973b7f42cbf6d4b3840c28765519154efa43d4bf95999d9ba31061`
- settlement manifest SHA-256: `4265f148f40e9be2fe4ce3294139df933c902fb3c4c5334579ab13b06be2e001`

Target HJC / SED were acquired only after an immutable PRE_HJC prediction freeze existed.

## Primary comparison

| Metric | v0.2 control | v1.1-P candidate |
|---|---:|---:|
| ◎ win | 34 | 34 |
| ◎ top2 | 50 | 50 |
| ◎ top3 | 65 | 69 |
| win ROI | 0.7935 | 0.7917 |
| Q2 hits | 23 | 23 |
| Q2 ROI | 0.5954 | 0.6384 |

The polarity gate changed the axis in 14 / 108 races.

On those 14 changed-axis races:

- ◎ win: 2 -> 2
- ◎ top2: 5 -> 5
- ◎ top3: 6 -> 10
- Q2 ROI: 0.4786 -> 0.8107
- Q4 ROI: 0.2393 -> 1.1482
- Trio A6 ROI: 0.6250 -> 1.5917
- direct finish comparison: v0.2 better in 8 races, v1.1-P better in 6 races

The top-five polarity bootstrap did not establish a stable separation:

- positive-minus-negative win-rate difference: `0.0156`, 95% CI `[-0.0726, 0.0972]`
- positive-minus-negative top3-rate difference: `0.0520`, 95% CI `[-0.0701, 0.1621]`

Both intervals include zero.

## Decision

**REPEAT_UNCHANGED.**

This block is encouraging for top3 containment and Q2 economics, especially on
the 14 races where the axis actually changed. It does not justify promotion:
win count and top2 count were unchanged, changed-axis direct finish comparison
was 8-6 in favor of the control, and the preregistered polarity bootstrap is
not conclusive.

Therefore:

- keep the `BaseGood - HorseGood <= 0.04` axis guard unchanged;
- keep family-vote aggregation and polarity collapse unchanged;

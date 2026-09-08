# RaceNote Blind Historical Backtest Settlement — 2025-08-23 v0.1

## Status

**SETTLED AFTER FULL-DAY PREDICTION FREEZE**

Sequence preserved:

```text
target set freeze
 -> RaceNote all-race acquisition (Issue #489 / run 34190369052)
 -> Reader View v0.1 round-trip 36/36 PASS
 -> prediction freeze commit fc09b47d7db233eff0450220861dec17da683799
 -> HJC acquisition (Issue #490 / run 34190672923)
 -> deterministic settlement
```

Prediction logic remained `provisional_handoff_v0.1_unweighted`. No 2025-08-23 target result, final odds/popularity, SED target result, HJC, or web result was read before the prediction freeze.

HJC source:

- `HJC250823.zip`
- SHA-256: `4d6a8e2bdf2862e323b20e6a4f3538d988e93deb292b29a3b8db21f88d5c2702`
- 36 race records

Settlement policy remained `RaceNote_Backtest_Settlement_Protocol_v0_1.md`:

- ① ◎単勝 1点
- ② ◎-○ / ◎-▲ 馬連 2点
- ③ ◎1頭軸、○ / ▲ / △1 / △2への3連複6点
- 100円均等

## 36-race summary

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| ① | 3,600円 | 3,380円 | 10/36 | 27.78% | 93.89% |
| ② | 7,200円 | 2,890円 | 5/36 | 13.89% | 40.14% |
| ③ | 21,600円 | 22,840円 | 10/36 | 27.78% | 105.74% |
| ①+② | 10,800円 | 6,270円 | 12/36 | 33.33% | 58.06% |
| ①+③ | 25,200円 | 26,220円 | 18/36 | 50.00% | 104.05% |
| ①+②+③ | 32,400円 | 29,110円 | 18/36 | 50.00% | 89.85% |

## Confidence split

This is descriptive only; confidence is evidence confidence, not predicted hit probability.

### A — 3 races

| Pattern | Investment | Payout | Hit races | Return rate |
|---|---:|---:|---:|---:|
| ① | 300円 | 170円 | 1 | 56.67% |
| ② | 600円 | 0円 | 0 | 0.00% |
| ③ | 1,800円 | 0円 | 0 | 0.00% |
| ①+②+③ | 2,700円 | 170円 | 1 | 6.30% |

### B — 27 races

| Pattern | Investment | Payout | Hit races | Return rate |
|---|---:|---:|---:|---:|
| ① | 2,700円 | 2,080円 | 6 | 77.04% |
| ② | 5,400円 | 2,590円 | 4 | 47.96% |
| ③ | 16,200円 | 22,230円 | 9 | 137.22% |
| ①+②+③ | 24,300円 | 26,900円 | 13 | 110.70% |

### C — 6 races

| Pattern | Investment | Payout | Hit races | Return rate |
|---|---:|---:|---:|---:|
| ① | 600円 | 1,130円 | 3 | 188.33% |
| ② | 1,200円 | 300円 | 1 | 25.00% |
| ③ | 3,600円 | 610円 | 1 | 16.94% |
| ①+②+③ | 5,400円 | 2,040円 | 4 | 37.78% |

The confidence split is much too small and noisy for policy changes. In particular, the weak A sample and strong B trio return must not be turned into a rule from this batch.

## Pooled reference with the earlier 2025-08-24 3-race PoC

This is only a directional reference because the 3-race PoC and the full-day batch were selected differently.

| Pattern | Investment | Payout | Hit races | Return rate |
|---|---:|---:|---:|---:|
| ① | 3,900円 | 3,570円 | 11/39 | 91.54% |
| ② | 7,800円 | 3,520円 | 6/39 | 45.13% |
| ③ | 23,400円 | 24,340円 | 11/39 | 104.02% |
| ①+② | 11,700円 | 7,090円 | 13/39 | 60.60% |
| ①+③ | 27,300円 | 27,910円 | 19/39 | 102.23% |
| ①+②+③ | 35,100円 | 31,430円 | 19/39 | 89.54% |

## Interpretation

- The first full-day blind batch does **not** show an immediately broken prediction layer.
- ③ alone and ①+③ exceeded 100% in this 36-race batch, while ② was weak. This is an observation, not a tuning instruction.
- The combined 39-race reference remains too small for stable venue/class/confidence/bet-type conclusions.
- Keep `provisional_handoff_v0.1_unweighted` and the frozen ticket policy unchanged for the next untouched historical batch.
- Accumulate substantially more races before changing prediction weights, confidence calibration, or dropping/adding a wager group.

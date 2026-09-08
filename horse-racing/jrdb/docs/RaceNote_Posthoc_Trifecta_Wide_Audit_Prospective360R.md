# RaceNote Post-hoc Trifecta / Wide Audit — Prospective 360R

## Status

**POST-SETTLEMENT BETTING DIAGNOSTIC ONLY. NOT A BLIND-PROMOTABLE BETTING RULE.**

This audit reuses only already-settled prospective freezes and the normalized HJC/result cache. No prediction marks were changed.

## 1. Trifecta definition

`◎印3連単` is interpreted here as:

```text
1着: ◎
2着: ○ / ▲ / △1 / △2
3着: ○ / ▲ / △1 / △2
```

with the same horse excluded from both second and third, for **12 tickets per race**, 100 yen each.

Because v0.3 only reorders the same four opponent horses, this 12-ticket formation is identical under v0.2 and v0.3 for the July/August sample.

## 2. Trifecta result — all 360 prospective races

| Block | Races | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|---:|
| Mar 2025 | 72 | 86,400 | 119,480 | 11 | **138.29%** |
| Jun 2025 | 72 | 86,400 | 41,480 | 5 | 48.01% |
| Jul 2025 | 72 | 86,400 | 134,850 | 12 | **156.08%** |
| Aug 2025 | 144 | 172,800 | 84,110 | 14 | 48.67% |
| **Total** | **360** | **432,000** | **379,920** | **42** | **87.94%** |

The pooled return is below break-even and the block dispersion is extreme. The result is payout-tail dependent and should not be interpreted as a stable positive-expectation rule.

For the v0.3-valid July+August 216R subset only:

- investment: 259,200 yen
- payout: 218,960 yen
- hit races: 26
- return: **84.48%**

## 3. Wide definition

`◎-妙味枠 ワイド` means:

- wager only when v0.3 had `▲妙味=yes` / `value_role=true`;
- one wide ticket: `◎ - v0.3 ▲`;
- 100 yen per eligible race;
- no wager when v0.3 did not identify a value ▲.

The valid prospective sample begins in July 2025 because the value-role semantics did not exist in the March/June freezes.

## 4. ◎-妙味▲ wide — July + August 216R

| Block | Eligible races | Investment | Payout | Hits | Return |
|---|---:|---:|---:|---:|---:|
| Jul 72R | 21 | 2,100 | 3,990 | 5 | **190.00%** |
| Aug 144R | 63 | 6,300 | 3,390 | 4 | 53.81% |
| **Total** | **84** | **8,400** | **7,380** | **9** | **87.86%** |

The July result did not replicate in August.

## 5. Same-race baseline comparison

For the same 84 races, compare the wide ticket against the ordinary pure-rank P3 horse that v0.2 would have used as ▲:

- pure-P3 wide payout: 7,600 yen
- investment: 8,400 yen
- return: **90.48%**

Thus the current value-role rule did **not** improve pooled wide economics versus pure P3 on the same eligible races.

### Actual role-change races only

There were 61 races where the value horse came from pure P4/P5 and therefore actually replaced the ordinary P3 horse.

- value-▲ wide: 6,100 -> 5,490 = **90.00%**, 6 hits
- pure-P3 wide: 6,100 -> 5,710 = **93.61%**, 12 hits

By block:

- July changed 16R: value ▲ 169.38% vs pure P3 43.13%
- August changed 45R: value ▲ 61.78% vs pure P3 111.56%

This confirms strong regime/block instability in the current value selector.

## 6. Interpretation

1. **◎1着固定12点3連単** is not profitable pooled at 360R (87.94%) and is highly volatile by block.
2. **◎-妙味▲ wide** is also below break-even pooled at 87.86% across 84 eligible races.
3. The wide comparison reinforces the prior conclusion that the semantic idea `▲ = 妙味役` can remain, but the current mechanical value selector is not yet stable enough for production.
4. These are post-hoc betting diagnostics. Any new formation or filter discovered here must be frozen before testing on a later untouched block.

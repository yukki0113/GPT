# RaceNote BTDAY-0030〜0032 Baseline Replication Review v0.1

## Status

**POST-HOC BASELINE REPLICATION — NOT A v0.4.2 vs v0.4.3 A/B TEST**

BTDAY-0030〜0032ではv0.4.2のみが結果前Freezeされ、v0.4.3はFreezeされていない。
したがって本レビューはv0.4.3の成績検証には使用しない。

目的は、0023〜0029で発見・RetestしたHierarchy / Coverage構造が、
追加のv0.4.2 baseline 96Rでも同じ方向に現れるか確認すること。

## Scope

- BTDAY-0030: 2026-09-19 / 24R
- BTDAY-0031: 2026-08-30 / 36R
- BTDAY-0032: 2026-03-01 / 36R
- total: **96R**

All:
- RaceNote-Human-Context-Reader-0.4.2-candidate
- rrdb-recommendation-signals-v0.3
- FROZEN_CLEAN_BLIND

## Mechanical population

Hierarchy candidate:
- 0030: 10R
- 0031: 17R
- 0032: 17R
- total: **44R**

Winner role:
- ○ 18
- ▲ 6
- △1 10
- △2 10

Coverage:
- coverage-failure race: **70 / 96**
- missed Top3: **87頭**
- 3着無印 detailed review: **39頭**

## Hierarchy result

- REVERSAL_WARRANTED: **4**
- NARROW_GAP: **11**
- PRE_RACE_JUSTIFIED: **23**
- SINGLE_SHOT_SUCCESS_NO_PROMOTION: **6**
- PROMOTION_WARRANTED: **0**

Clear correction:
- **4 / 44 = 9.1%**

Boundary:
- **11 / 44 = 25.0%**

No clear correction / ▲ role success:
- 23 PRE_RACE_JUSTIFIED
- 6 SINGLE_SHOT_SUCCESS_NO_PROMOTION
- total **29 / 44 = 65.9%**

### Comparison with prior sets

Discovery 0023〜0026:
- clear 12 / 64 = 18.8%
- boundary 11 / 64 = 17.2%
- no clear correction 41 / 64 = 64.1%

Retest 0027〜0029:
- clear 7 / 45 = 15.6%
- boundary 6 / 45 = 13.3%
- no clear correction 32 / 45 = 71.1%

Replication 0030〜0032:
- clear 4 / 44 = 9.1%
- boundary 11 / 44 = 25.0%
- no clear correction 29 / 44 = 65.9%

Combined mechanical Hierarchy population:
- **153R**
- clear correction: **23 / 153 = 15.0%**
- boundary: **28 / 153 = 18.3%**
- no clear correction / ▲ role success: **102 / 153 = 66.7%**

The direction remains stable:
**mechanical “winner != ◎” is mostly not a correctable ◎ failure.**

## ▲ replication

This set:
- ▲ winner: **6R**
- SINGLE_SHOT_SUCCESS_NO_PROMOTION: **6**
- promotion: **0**

Across 0023〜0032:
- ▲ winner: 26R
- single-shot success without promotion: **23**
- promotion warranted: **2**
- ambiguous: **1**

Thus **23 / 26 = 88.5%** of observed ▲ wins are best interpreted as the role working,
not as evidence that ▲ should have been promoted to ◎/○.

This strongly supports preserving ▲ as a distinct role.

## Reproduced Hierarchy correction patterns

Clear reversals in this set:
1. 0030 中山9R — same-distance 1200m win / can-win evidence underweighted.
2. 0031 札幌4R — 2000m direct-condition evidence underweighted versus strong but 2600m-derived ◎ evidence.
3. 0032 阪神9R — same 2200m 2nd + REAR_HIGH_LAST3F90 + strong training.
4. 0032 阪神10R — same 1800m 2nd versus ◎'s 1600m 3rd.

All four are variants of the already observed pattern:
**race_model / target condition and final hierarchy must remain semantically consistent.**

## Coverage third-place review

39 unmarked third-place horses:
- SWAP_CANDIDATE: **8 / 39 = 20.5%**
- COMPLETE_MISS: **30 / 39 = 76.9%**
- AMBIGUOUS: **1 / 39 = 2.6%**

Prior:
- Discovery 0023〜0026: SWAP 32/68 = 47.1%
- Retest 0027〜0029: SWAP 7/24 = 29.2%
- Replication 0030〜0032: SWAP **8/39 = 20.5%**

Combined 0023〜0032 detailed 3着無印:
- total 131
- SWAP 47 = **35.9%**
- COMPLETE_MISS 73 = **55.7%**
- AMBIGUOUS 11 = **8.4%**

The SWAP rate has fallen in each new independent block:
**47.1% -> 29.2% -> 20.5%**.

Therefore a broad all-field Coverage rescan is not supported.

## What the successful Coverage swaps look like

The 8 SWAP cases remain highly interpretable:
- direct same/near-condition performance;
- ability close enough to △ boundary;
- selected △2 has weaker direct evidence;
- hidden strength is supporting evidence, not the sole reason.

Examples:
- 0030 阪神4R アトラクティーボ — recent障害2着 versus support boundary 4着.
- 0031 中京11R ハピネスサンライズ — same 1400m4着, ability equal to support boundary.
- 0031 新潟6R ヴァイヴァーイ — same 1800m win + FRONT_SURVIVE.
- 0032 小倉5R セイカユウヒ — same 1200m5着 versus △2 from 1600m.
- 0032 小倉9R ゼンノインヴォーク — same 2000m4着 versus △2 from 1800m.
- 0032 阪神8R フェイトライン — prior 1800m2着/4着 while support boundary came from weaker recent adjacent-distance runs.

## Updated research interpretation

### Hierarchy

**Strongly replicated.**

Keep:
- race_model consistency check;
- direct-condition comparison;
- runs-well vs can-win distinction;
- visible result vs hidden content comparison;
- conservative ▲ promotion gate.

### Coverage

**Replicated only as a narrow gate.**

The evidence now argues against:
- broad whole-field re-search;
- hidden-strength-only challenger generation;
- treating every unmarked Top3 horse as a recoverable miss.

The supported form is:

> After provisional △2, only consider an unmarked challenger when it has
> materially direct evidence for today's condition and no large ability gap
> versus the support boundary. Hidden/RRDB/trouble evidence may strengthen,
> but not create, the challenger case by itself.

## Consequence for v0.4.3

No v0.4.3 mark was frozen for BTDAY-0030〜0032.
Therefore this review **must not be counted as A/B validation** and must not
be used to claim v0.4.3 outperformed v0.4.2.

It does, however, provide independent retrospective support for the semantic
design already frozen in:
`FORECAST_HUMAN_CONTEXT_READER_v0_4_3_CANDIDATE.md`.

No further expansion of the v0.4.3 rule set is warranted from this review.

Next clean evidence should be new unused BTDAYs with both 0.4.2 and 0.4.3
frozen before result access.

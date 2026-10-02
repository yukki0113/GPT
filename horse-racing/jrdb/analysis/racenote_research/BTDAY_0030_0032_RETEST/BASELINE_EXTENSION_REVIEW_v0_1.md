# RaceNote BTDAY-0030〜0032 Baseline Extension Review v0.1

## Scope

- BTDAY-0030: 2026-09-19 / 24R
- BTDAY-0031: 2026-08-30 / 36R
- BTDAY-0032: 2026-03-01 / 36R
- total: **96R**

All forecasts:
- `RaceNote-Human-Context-Reader-0.4.2-candidate`
- `rrdb-recommendation-signals-v0.3`
- FROZEN_CLEAN_BLIND

These sets are **not valid v0.4.2 vs v0.4.3 A/B evidence**, because only v0.4.2 was Frozen before result access.
They remain valid additional blinded baseline evidence for Hierarchy/Coverage research.

## Mechanical population

Hierarchy candidate:
- 0030: 10R
- 0031: 17R
- 0032: 17R
- total **44R**

winner role:
- ○ 18
- ▲ 6
- △1 10
- △2 10

Coverage failure:
- 0030: 17R / 22 missed Top3
- 0031: 28R / 34 missed Top3
- 0032: 25R / 31 missed Top3
- total **70R / 87 missed Top3**

3着無印:
- **39頭**

## Hierarchy review

- REVERSAL_WARRANTED: **5**
- PROMOTION_WARRANTED (▲): **1**
- NARROW_GAP: **6**
- PRE_RACE_JUSTIFIED: **27**
- SINGLE_SHOT_SUCCESS_NO_PROMOTION: **5**

Clear correction:
- 6 / 44 = **13.6%**

Boundary:
- 6 / 44 = **13.6%**

No clear correction:
- 32 / 44 = **72.7%**

### Cumulative Hierarchy evidence

Discovery 0023〜0026:
- clear 12/64 = 18.8%
- boundary 11/64 = 17.2%
- no clear correction 41/64 = 64.1%

Retest 0027〜0029:
- clear 7/45 = 15.6%
- boundary 6/45 = 13.3%
- no clear correction 32/45 = 71.1%

Baseline extension 0030〜0032:
- clear 6/44 = 13.6%
- boundary 6/44 = 13.6%
- no clear correction 32/44 = 72.7%

Combined 0023〜0032 reviewed Hierarchy population:
- clear **25 / 153 = 16.3%**
- boundary **23 / 153 = 15.0%**
- no clear correction **105 / 153 = 68.6%**

Hierarchy hypothesis remains stable.

### ▲ role

This set:
- ▲ winner 6
- single-shot success 5
- promotion warranted 1

Cumulative:
- Discovery: 9 success / 1 promotion / 1 ambiguous
- Retest 27〜29: 8 success / 1 promotion
- 30〜32: 5 success / 1 promotion

Across 26 ▲ winners:
- **22 single-shot successes**
- **3 promotion misses**
- **1 ambiguous**

The independent ▲ role is strongly supported.

### Repeated clear correction patterns

- direct-condition evidence:
  - 0030 中山9R
  - 0031 札幌4R
  - 0032 中山7R
  - 0032 阪神9R
  - 0032 阪神10R

- ▲ promotion gate:
  - 0032 阪神6R
  - same-distance win + training up vs ◎ same-distance 4th

Again, correction is concentrated in semantic comparison consistency, not a broad re-ranking failure.

## Coverage 3rd-place review

This set:
- SWAP_CANDIDATE: **8 / 39 = 20.5%**
- COMPLETE_MISS: **25 / 39 = 64.1%**
- AMBIGUOUS: **6 / 39 = 15.4%**

Earlier:
- Discovery 0023〜0026: SWAP 32/68 = 47.1%
- Retest 0027〜0029: SWAP 7/24 = 29.2%

0030〜0032 falls further to **20.5%**.

Combined 3着無印 0023〜0032:
- SWAP **47 / 131 = 35.9%**
- COMPLETE **68 / 131 = 51.9%**
- AMBIGUOUS **16 / 131 = 12.2%**

### Coverage conclusion

The narrow challenger hypothesis still finds real cases, especially:
- same/near condition direct evidence;
- ability close to △2;
- obstacle direct experience;
- direct win evidence.

But most misses in this set are **not recoverable without hindsight**.

Therefore:
- do not widen the five-horse candidate set;
- do not rescan based on hidden-strength flags alone;
- keep the v0.4.3 Coverage gate conservative;
- direct-condition evidence + ability proximity should remain the core entry condition.

## Research implication

This third independent 96R block strengthens the current v0.4.3 design:

1. **Hierarchy consistency pass: supported**
2. **▲ promotion gate: supported**
3. **narrow Coverage challenger gate: supported only as a small boundary correction**
4. Broad Coverage expansion: **not supported**

No change to v0.4.2 baseline is made from this post-result review.
No retrospective v0.4.3 A/B result should be claimed for 0030〜0032.

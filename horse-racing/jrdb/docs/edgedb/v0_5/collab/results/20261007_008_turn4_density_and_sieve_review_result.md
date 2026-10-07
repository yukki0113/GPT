# EdgeDB v0.5 Turn 4 — Density and Sieve Review

Status: PASS  
Recommendation: `NO_STATIC_SIEVE_ACCEPTED__OOS_TIERING_SHADOW_ONLY`  
Production impact: NONE

## Objective

Turn 4 compared candidate-selection / presentation policies against the frozen 2026 replay without changing the underlying 1,620-candidate research inventory.

The comparison was split into two scientific classes.

### STATIC_2024_2025_ONLY

These policies use only information that existed before the 2026 replay:

- 2024-2025 support
- 2024-2025 place ROI
- place ROI after removing the largest place payout
- 2024-2025 longshot-place evidence

Because their membership does not use 2026 outcomes, the frozen 2026 replay can be used as evaluation evidence.

### OOS_INFORMED_DIAGNOSTIC

These policies use the Turn 3 2026 OOS labels.

They are useful as design diagnostics, but **must not be described as OOS-validated filters**, because their membership is itself defined using the 2026 outcomes.

They require a later true-forward period.

---

## Baseline display density

The full frozen cohort contains:

- candidates: **1,620**
- 2026 match rows: **15,330**
- total 2026 runners: **36,706**
- runners with at least one signal: **12,633**
- average signals per all runner: **0.418**
- average signals per signaled runner: **1.213**
- maximum signals on one runner: **5**

Runner density:

| Signals on runner | Runners | Share of all runners |
|---|---:|---:|
| 0 | 24,073 | 65.6% |
| 1 | 10,266 | 28.0% |
| 2 | 2,074 | 5.6% |
| 3 | 262 | 0.7% |
| 4+ | 31 | 0.08% |

This changes the interpretation of the original “1,620 candidates is too many” concern.

The research inventory is large, but **actual runner-level display density is modest**:

- almost two thirds of runners have no positive Edge;
- among runners with an Edge, most have only one;
- 3+ simultaneous positive signals are rare.

Therefore candidate count alone is not sufficient justification for an aggressive global sieve.

---

## Static-policy comparison

### P1 — 2024-2025 n >= 20

- candidates: **498**
- candidate retention: 30.7%
- 2026 match rows: 11,453
- Confirmed retention: **66.3%**
- Contradicted retention: **90.4%**
- 8+ popularity place-hit retention: **81.8%**
- 10+ popularity place-hit retention: **82.0%**

This is not a useful discriminator.

It removes one third of later-Confirmed candidates while retaining nine tenths of later-Contradicted candidates.

A simple n>=20 rule therefore reduces niche coverage much more effectively than it removes bad signals.

### P2 — 2024-2025 place ROI >= 120%

- candidates: **1,078**
- Confirmed retention: **54.1%**
- Contradicted retention: **47.1%**
- 8+ popularity place-hit retention: **48.8%**
- 10+ popularity place-hit retention: **45.9%**

Raising the ROI gate does not solve the problem.

It removes roughly half of both the later-positive and later-negative populations, while losing more than half of 2026 longshot place-hit coverage.

This is consistent with the project’s earlier concern that large ROI thresholds can discard useful market-miss conditions without reliably distinguishing durability.

### P3 — place ROI excluding largest payout >= 100%

- candidates: **237**
- Confirmed retention: **11.2%**
- Contradicted retention: **23.1%**
- 8+ popularity place-hit retention: **19.1%**
- 10+ popularity place-hit retention: **15.5%**

This is much too destructive.

Removing jackpot dependence as a hard requirement eliminates many later-Confirmed conditions and most longshot evidence.

It directly conflicts with the EdgeDB purpose of retaining potentially meaningful market-miss cases.

### P4 — stable lane + 10+ popularity rescue

Stable lane:

`n>=20 AND place ROI ex-top1>=100%`

Discovery rescue:

`n<20 AND >=1 place hit at popularity 10+ AND place ROI>=120%`

Result:

- candidates: **564**
- Confirmed retention: **21.4%**
- Contradicted retention: **26.0%**
- 8+ popularity place-hit retention: **24.6%**
- 10+ popularity place-hit retention: **21.1%**

Even with an explicit longshot rescue lane, this approach still discards too much useful later evidence.

### P5 — stable lane + 8+ popularity rescue

The broader rescue increases candidates to **747**, but still retains only:

- Confirmed: **28.6%**
- 8+ popularity place hits: **29.4%**
- 10+ popularity place hits: **26.8%**

This remains too aggressive.

---

## Static-policy conclusion

None of the tested 2024-2025-only gates satisfies the desired tradeoff:

> materially reduce noise while preserving later-Confirmed and market-miss signals and preferentially removing later-Contradicted signals.

The strongest negative finding is simple `n>=20`.

It preserves 90% of later-Contradicted candidates, so sample size alone is not the missing discriminator.

The same is true, in different ways, for:

- ROI >= 120%
- ex-top1 ROI >= 100%
- two-lane longshot-rescue filters

Therefore **no new static candidate gate should be frozen from Turn 4**.

---

## 2026 OOS-informed diagnostic policies

These are not valid OOS tests, but they are useful for designing future presentation state.

### D1 — exclude only CONTRADICTED

- candidates: **1,516**
- match rows: **10,901**
- Confirmed retention: **100%**
- Contradicted retention: **0%**
- 8+ popularity place-hit retention: **84.7%**
- 10+ popularity place-hit retention: **85.1%**

This is a notably favorable diagnostic shape.

It removes only 6.4% of candidate definitions but reduces match rows by about 29%, because the Contradicted group tends to contain high-frequency conditions.

However, this result **cannot be claimed as validated**, because “CONTRADICTED” was assigned using the same 2026 outcomes.

It is a candidate for future-forward shadow suppression.

### D2 — CONFIRMED or STILL_PLAUSIBLE only

- candidates: **292**
- match rows: **6,148**
- 8+ popularity place-hit retention: **65.1%**
- 10+ popularity place-hit retention: **65.5%**

This would make the displayed set much smaller, but it is more aggressive and leaves 901 currently under-observed candidates outside the preferred tier.

It is better interpreted as a high-confidence presentation tier than as a deletion rule.

---

## Signal-row returns are diagnostic only

For completeness, the signal-row place ROI values were:

- baseline: 72.1%
- n>=20: 74.7%
- ROI>=120 gate: 66.5%
- ex-top1 gate: 67.6%
- 10+ rescue: 64.1%
- 8+ rescue: 64.6%
- OOS exclude Contradicted: 80.7%
- OOS Confirmed/Plausible only: 107.5%

These must **not** be interpreted as standalone betting-strategy ROI.

A runner can match multiple candidates, so signal rows can duplicate the same horse. EdgeDB remains a forecast memo / decision-support system, not an auto-betting strategy.

---

## Recommended v0.5 state after Turn 4

### Research inventory

Keep the complete **1,620-candidate frozen inventory**.

Do not delete:

- MICRO candidates;
- one-hit/jackpot candidates;
- T2 candidates solely for being numerous;
- conditions with insufficient 2026 support.

### Static gate

No additional static sieve is accepted.

The frozen positive discovery rule remains:

`n >= 5 AND combined 2024-2025 place ROI >= 100%`

for the v0.5 research inventory.

### Presentation / shadow state

Use Turn 3 labels as **research tiers only**:

- `CONFIRMED` — high-priority shadow candidate
- `STILL_PLAUSIBLE` — positive shadow candidate
- `DECAYING` — observe
- `INSUFFICIENT_OOS` — unresolved / observe
- `CONTRADICTED` — suppression candidate in shadow only

Do not hard-delete any group.

The most promising next hypothesis is:

> suppress CONTRADICTED conditions from the default presentation while retaining them in the research database.

That hypothesis must be validated prospectively on races after the frozen replay endpoint.

---

## Why this is a useful result

Turn 4 did not produce a neat numerical cutoff, but that is scientifically useful.

The original concern was that 1,620 positive candidates probably implied intolerable production density and therefore required a stronger in-sample gate.

The replay shows two things:

1. candidate-count density is not the same as runner-display density;
2. simple pre-2026 thresholds do not successfully separate later-good from later-bad signals.

So forcing a stronger static gate now would mostly be aesthetic pruning, not evidence-based improvement.

The better path is to retain the broad research inventory and move filtering pressure to a validated presentation-state layer.

---

## Artifact

Actions run:

`37615460773`

Artifact:

`11479194562`

Name:

`edgedb-v05-turn4-sieve-pr-1899`

Digest:

`sha256:73d66fc13069bca4d13317e463314f53e9b9de16bb7a46159b30334a2ec3b64c`

Focused tests: **10 PASS**

Artifact contains:

- `v05_turn4_sieve_comparison.json`
- `v05_turn4_sieve_comparison.csv`

Production remains unchanged.

## Final recommendation

`NO_STATIC_SIEVE_ACCEPTED__OOS_TIERING_SHADOW_ONLY`

Turn 4 is complete.

The next scientifically clean step is a true-forward shadow validation beginning strictly after the frozen 2026 replay endpoint, using the Turn 3 diagnostic tiers without changing their definitions after outcomes are observed.

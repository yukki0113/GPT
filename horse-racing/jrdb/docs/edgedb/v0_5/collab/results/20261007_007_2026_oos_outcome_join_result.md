# EdgeDB v0.5 Turn 3 — 2026 OOS Outcome Join

Status: PASS  
Recommendation: `READY_FOR_TURN4_DENSITY_AND_SIEVE_REVIEW`  
Production impact: NONE

## Boundary

Turn 2 was fully frozen before any 2026 result data was opened.

Verified inputs:

- frozen cohort: 1,620 candidates
- cohort SHA-256: `a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9`
- Turn 2 match rows: 15,330
- Turn 2 match SHA-256: `0b99b90b745aef11655630ed2b1416f71c5664b1a3f133f08fd0d493b68b55f0`

Only after the match SHA was verified were canonical 2026 SED outcomes joined.

No candidate membership, condition, family, support class, freshness label, or 2024-2025 gate was modified.

## Result source and join audit

Canonical result source:

- Actions run: `37604723913`
- artifact: `11474018960`
- digest: `sha256:23080e983350cd61255d229315855cab29a492eef62e3ae1df6c88bbe164c516`
- 84 SED archives
- 36,706 runner result rows

Join result:

- Turn 2 match rows: 15,330
- joined rows: 15,330
- missing result joins: 0

The evaluation follows the same v0.5 outcome semantics used in discovery:

- abnormal/non-completed rows do not enter the evaluation denominator;
- win hit = normal finish position 1;
- place hit = positive settled place payout;
- ROI is yen returned per 100-yen stake, numerically expressed as percent.

## Diagnostic OOS labels

These labels are descriptive only and are not an adoption/pruning gate.

- `INSUFFICIENT_OOS`: n2026 < 5
- `CONFIRMED`: n>=5, place ROI>=100%, and place-rate delta > -3pt
- `STILL_PLAUSIBLE`: n>=5 and either place ROI>=100% or place-rate delta > -3pt, excluding CONFIRMED
- `CONTRADICTED`: n>=20, place ROI<100%, place-rate delta <= -3pt, and place-ROI delta <= -20pt
- `DECAYING`: remaining n>=5 candidates

The -3pt / -20pt diagnostics reuse the conservative degradation thresholds already used in v0.5 negative-Edge research. No new production filter was introduced.

## Candidate-level OOS result

| Label | Candidates |
|---|---:|
| CONFIRMED | 98 |
| STILL_PLAUSIBLE | 194 |
| DECAYING | 323 |
| CONTRADICTED | 104 |
| INSUFFICIENT_OOS | 901 |
| **Total** | **1,620** |

Of the 1,620 frozen candidates:

- 719 reached n>=5 in 2026;
- 901 remain below n=5;
- 232 had no 2026 matched runner at all.

This is an important limitation: Turn 3 does not justify treating all 1,620 candidates as decisively validated or rejected.

## Family breakdown

| Family | Candidates | Confirmed | Plausible | Decaying | Contradicted | Insufficient |
|---|---:|---:|---:|---:|---:|---:|
| T1 | 100 | 17 | 29 | 11 | 27 | 16 |
| T2 | 1,102 | 55 | 113 | 239 | 25 | 670 |
| T3 | 93 | 1 | 10 | 11 | 6 | 65 |
| T4 | 117 | 7 | 18 | 22 | 24 | 46 |
| T5 | 22 | 6 | 3 | 6 | 0 | 7 |
| T6 | 186 | 12 | 21 | 34 | 22 | 97 |

The largest unresolved population remains T2: 670 of 1,102 candidates still have n<5 in the 2026 replay.

## Support-class breakdown

| 2024-2025 support | Candidates | Confirmed | Plausible | Decaying | Contradicted | Insufficient |
|---|---:|---:|---:|---:|---:|---:|
| MICRO | 650 | 9 | 24 | 59 | 4 | 554 |
| SMALL | 472 | 24 | 52 | 117 | 6 | 273 |
| MEDIUM | 317 | 37 | 61 | 124 | 24 | 71 |
| LARGE | 181 | 28 | 57 | 23 | 70 | 3 |

This is one of the clearest Turn 3 findings: OOS identifiability is strongly support-dependent. MICRO candidates are mostly still untestable in one 2026 season, while LARGE candidates are almost all testable and include both strong confirmations and strong contradictions.

## Representative examples

### Confirmed examples

- `v05-3b476ec3c68613ca8bc05704` — T2, エピファネイア産駒 × 小倉芝2000m  
  2024-25: n=60, place ROI 129.7%  
  2026: n=23, place rate 52.2%, place ROI 190.0%, delta place rate +17.2pt.

- `v05-21a4571c6947505d6d9f87f0` — T6, ブリックスアンドモルタル産駒 × 芝 × SOFT_OR_WORSE  
  2024-25: n=200, place ROI 101.0%  
  2026: n=80, place rate 28.8%, place ROI 217.8%.  
  Maximum 2026 place payout: 8,740 yen.

- `v05-cea7631adaa9b418e927baf8` — T4, イスラボニータ産駒 × dirt-to-turf  
  2024-25: n=65, place ROI 122.6%  
  2026: n=22, place ROI 388.2%.

These remain diagnostic examples; large payouts can materially affect ROI and are not treated as proof by themselves.

### Still plausible examples

- `v05-7bfd3cf14969877bc589a27c` — T1, 中山ダート1200m 7枠  
  2024-25: n=470, place ROI 108.0%  
  2026: n=195, place rate improved by +1.8pt but place ROI fell to 76.5%.

- `v05-0cdf0a7051d2145310ce0270` — T3, モーリス産駒 × distance extend  
  2024-25: n=421, place ROI 106.2%  
  2026: n=102, place rate improved by +2.1pt, place ROI 88.5%.

These illustrate why Performance and Value must remain separate: outcome frequency can remain healthy while betting return weakens.

### Contradicted examples

- `v05-95afa1cce326c07e386b539a` — T1, 阪神ダート1800m 6枠  
  2024-25: n=270, place ROI 101.9%  
  2026: n=175, place rate -6.5pt, place ROI 51.9%.

- `v05-5056f673a5dfab937d7ef5ff` — T6, ベンバトル産駒 × 芝 × GOOD  
  2024-25: n=80, place ROI 148.3%  
  2026: n=159, place rate -11.8pt, place ROI 62.7%.

- `v05-3b4c79f7344f494d86fa910c` — T1, 新潟ダート1800m 4枠  
  2024-25: n=248, place ROI 119.0%  
  2026: n=96, place rate -3.6pt, place ROI 51.5%.

These have enough 2026 support to be meaningfully adverse evidence, but Turn 3 still does not delete them.

## Freshness observation

The existing 2024-2025 freshness labels do not cleanly separate 2026 winners from losers. Both confirmed and contradicted candidates exist within CURRENT, EMERGING, VOLATILE, and INSUFFICIENT_HISTORY groups.

Therefore freshness should not be promoted into a hard pruning rule merely from this replay.

## Fingerprints and artifact

- joined match SHA-256: `4f8a37bda9f8d39931733b2e0125f5497da1dfd36f6acdf890daeebf72a1176e`
- candidate evaluation SHA-256: `6c3f13b071e1c2b0d902c1262b020597b547c3e7e665f3bd1166c3af77097b6b`

Actions:

- run: `37614611257`
- artifact: `11478468034`
- name: `edgedb-v05-2026-oos-eval-pr-1898`
- digest: `sha256:f10034cf6d2d730dcb3d76b6c9be41c90d36e61e49c94b70ab7458f296eb9f13`

The artifact contains row-level joined matches, the 1,620-row candidate evaluation, CSV, summary, and audit.

## Recommendation

`READY_FOR_TURN4_DENSITY_AND_SIEVE_REVIEW`

Turn 3 is complete.

Turn 4 may now compare candidate-selection / presentation-policy alternatives against the frozen 2026 replay. It must not reinterpret Turn 3 labels as automatic keep/drop decisions.

Production remains unchanged.

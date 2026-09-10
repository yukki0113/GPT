# JRDB Edge v0.2 Status Semantics Full Audit — 2026-09-10

## 1. Purpose

Validate the Full 2010–2025 rebuild after the v0.2 status-semantics change that separates temporal `WATCH` from statistical rejection.

This audit compares the previous Full build (#723) with the new Full build (#822). It is a structural/status audit only. It does not reinterpret Edge quality or tune statistical thresholds.

## 2. Compared builds

| Item | Previous Full | New Full |
|---|---|---|
| Issue | #723 | #822 |
| Run | `34363072861` | `34429085356` |
| Registry version | `edge-v0.2-human-residual-full-2010-2025-f` | `edge-v0.2-status-semantics-full-2010-2025-a` |
| Head SHA | `1565ca103cdf290af6c17a457bfa38a5b8180cca` | `13063524c05700f1c520dad13781859c6765eda3` |
| Artifact ID | `10112738032` | `10135816871` |
| Artifact digest | `sha256:99da3185c7b3017e67b7a31e2ab198b6c8b03a1586e87ae8228a7c9d89d486af` | `sha256:d570cb8b6592d5e32aa8529d5f0bdd512577dabfaea47178dc8d9a5c63b13b72` |
| Years | 2010–2025 | 2010–2025 |
| Template version | `2026-09-09.v2.2` | `2026-09-09.v2.2` |

Both workflow runs completed successfully.

## 3. Structural equivalence

Deterministic comparison of the two `edge_registry.sqlite` files established:

- Stored Edge count: `8182 -> 8182`.
- Edge ID sets are exactly identical.
- ACTIVE Edge IDs are exactly identical: `2572 -> 2572`.
- PROVISIONAL Edge IDs are exactly identical: `64 -> 64`.
- DECAYING Edge IDs are exactly identical: `74 -> 74`.
- Live Edge count is unchanged: `2636 -> 2636`.
- `edge_metric_snapshot` rows are identical in all fields.
- Statistical-guard core evidence is unchanged; its internal `statistical_status` distribution remains the same. The change is applied only to the final Registry status semantics.

The only final-status transitions are:

| Previous status | New status | Count |
|---|---|---:|
| ACTIVE | ACTIVE | 2572 |
| PROVISIONAL | PROVISIONAL | 64 |
| DECAYING | DECAYING | 74 |
| WATCH | WATCH | 1663 |
| WATCH | REJECTED | 3809 |

For the 3,809 reclassified records, `confidence_band` changes to `R`, consistent with final rejected semantics. No performance/value metric changed.

## 4. Family-level result

| Family | ACTIVE | PROVISIONAL | DECAYING | WATCH | REJECTED |
|---|---:|---:|---:|---:|---:|
| COURSE | 172 | 0 | 0 | 0 | 242 |
| HUMAN | 91 | 0 | 31 | 721 | 44 |
| PEDIGREE | 1450 | 35 | 0 | 541 | 2692 |
| RECENT | 197 | 0 | 43 | 121 | 24 |
| TRANSITION | 662 | 29 | 0 | 280 | 807 |
| **Total** | **2572** | **64** | **74** | **1663** | **3809** |

HUMAN and RECENT remain active at exactly the same counts as the previous Full build. The status-semantics change therefore does not remove the v0.2 gains that activated those families.

## 5. Template-level WATCH / REJECTED split

| Family | Template / Edge cluster | WATCH | REJECTED |
|---|---|---:|---:|
| COURSE | COURSE_EXACT_FRAME_V2 | 0 | 214 |
| COURSE | COURSE_FRAME_V1 | 0 | 28 |
| HUMAN | JOCKEY_VENUE_DISTANCE_V2 | 721 | 44 |
| PEDIGREE | BROODMARE_SIRE_SURFACE_DISTANCE_V2 | 21 | 458 |
| PEDIGREE | SIRE_AGE_V2 | 159 | 214 |
| PEDIGREE | SIRE_BROODMARE_SIRE_V2 | 10 | 93 |
| PEDIGREE | SIRE_LINE_TURN_DISTANCE_V1 | 19 | 89 |
| PEDIGREE | SIRE_SURFACE_DISTANCE_V1 | 86 | 452 |
| PEDIGREE | SIRE_TRACK_CONDITION_V2 | 104 | 300 |
| PEDIGREE | SIRE_TURN_DISTANCE_V1 | 88 | 521 |
| PEDIGREE | SIRE_VENUE_SURFACE_DISTANCE_V2 | 54 | 565 |
| RECENT | RECENT_ROTATION_SURFACE_DISTANCE_V2 | 85 | 24 |
| RECENT | RECENT_STABLE_EVAL_SURFACE_DISTANCE_V2 | 18 | 0 |
| RECENT | RECENT_TRAINING_ARROW_SURFACE_DISTANCE_V2 | 8 | 0 |
| RECENT | RECENT_UPTREND_SURFACE_DISTANCE_V2 | 10 | 0 |
| TRANSITION | SIRE_DISTANCE_CHANGE_V1 | 102 | 178 |
| TRANSITION | SIRE_FRAME_TRANSITION_V1 | 98 | 528 |
| TRANSITION | SIRE_SURFACE_TRANSITION_V1 | 80 | 101 |

The remaining 1,663 WATCH records are exclusively temporal WATCH according to `edge_watch_audit.json`.

## 6. Statistical-reject diagnostics — corrected CI semantics

The production guard performs a q-value prepass before bootstrap evaluation. If a temporal ACTIVE/PROVISIONAL candidate has no non-neutral signal clearing its q threshold, bootstrap is intentionally skipped and CI fields remain null.

Therefore the correct decomposition of the 3,809 statistical rejects is:

- q-value prepass failed; bootstrap CI **not evaluated**: `3736` (98.08%).
- q-value prepass passed; bootstrap evaluated; final directional-CI gate not cleared: `73` (1.92%).
- Final temporal WATCH: `1663`.

The earlier wording `ALL_SIGNAL_FDR_AND_CI_FAIL` incorrectly treated missing CI as CI failure for q-prepass failures. The audit tool has been corrected to distinguish `FDR_FAIL_CI_NOT_EVALUATED` from an actual evaluated CI failure.

This correction does not change the Full build acceptance or any Registry status. It changes only the interpretation of why most statistical rejects stopped: most were rejected at the FDR prepass and never reached bootstrap evaluation.

## 7. Acceptance decision

**PASS — status-semantics migration accepted for v0.2.**

The Full rebuild confirms that the change is a semantic reclassification only:

- candidate/Edge population unchanged,
- ACTIVE/PROVISIONAL/DECAYING populations unchanged,
- live consumer population unchanged,
- metrics unchanged,
- 3,809 statistical downgrades moved from overloaded `WATCH` to `REJECTED`,
- 1,663 genuinely temporal candidates remain `WATCH`.

No statistical threshold change is authorized by this audit.

## 8. Next development point

With status semantics fixed, the next serving-layer research should evaluate whether a lower-confidence evidence tier can be defined without weakening the CONFIRMED/ACTIVE contract.

Because 3,736 statistical rejects never received bootstrap CI, such a tier must not assume those candidates also failed CI. A defensible experiment should prefilter candidates independently of any favorite example, then explicitly run additional directional bootstrap evaluation for that research-only pool before deciding whether any should become serving-eligible.

# JRDB Feature Audit — Stage C Report

Date: 2026-10-06  
Decision: **DESIGN_0_5_CANDIDATE**  
Base: main `e52f2ac4c76247b8f8be443464a161d8b143a67d`  
Scope: future Reader information architecture only; no active v0.4.6 change

## Evidence and method

This proposal uses the accepted 2023–2025 Stage B report, audit, catalog and checksum manifest. The cohort has 10,365 races, 142,737 runner entries, 141,523 valid-result entries and 73 catalogued scalar leaves. Stage B is descriptive; a strong quintile gap is not a weight or a claim of value against final prices. No race was re-predicted, no result inspected for the structural example, and no five-year extension was performed.

The machine policy contains one row per Stage B scalar leaf. Its `reader_leaf` is a catalogued v0.4.6 exposure path; the current state indicates the catalog path, not a newly verified assertion about every rendered prompt variant. Every row preserves its source record and provenance.

## Field-family decisions

| Family | Proposed normal Reader treatment | Evidence and caution |
|---|---|---|
| Ability and provider composites | Show IDM as the primary ability anchor. Group information and longshot indices in the same ability block as supporting provider views. Put total index in detail/provenance. Show JRDB marks only as detail of their parent index, never as extra independent votes. | IDM/total rank Spearman 0.952; IDM, total and information Q1–Q5 gaps 17.83, 19.46 and 19.77 points, with substantial market alignment. Correlation is high, while information and longshot semantics are not proven identical. |
| Jockey and stable | Show jockey index once; retain expected top-two rate in detail. Show stable index as secondary connection context. Attach jockey/stable marks to their numeric parent in detail. | Jockey pair Spearman 0.989 and top-1 overlap 0.959. Stable is a separate connection concept. |
| Pace and projected position | Lead with late pace numeric index; keep front/pace/position numeric indices as secondary shape. Suppress corresponding supplied rank in normal view. Present mid, last-3f and finish projected margin as a single trajectory, with order in detail; keep lane only as conditional context. Start index and late-break rate are conditional. | Pace late Q1–Q5 gap 10.28 points, with lower final-popularity correlation (-0.389). Numeric/rank ordering is near identical; projected finish order/margin correlation 0.992. Start and late-break gaps 2.96/2.21 points and have missingness. Exact rank matches are imperfect (late 87.98%), so source ranks remain inspectable. |
| Training and condition | Keep KYI training index prominent. Show CHA last clock and CYB condition as secondary distinct context. Display CYB training index and CHA total clock index in one shared workout block; the latter is detail only. Keep arrow, improvement and stable evaluation as context. Farm, raw CHA workout and CYB course/volume detail appear only when relevant. | KYI training Q1–Q5 gap 20.14 points. CHA last/CYB condition gaps 5.61/6.66. CHA total/CYB training had identical observed values and coverage on 136,601 valid-result entries; KYI/CYB training correlation was only 0.159. Equality is sample observed, not a formula guarantee. |
| Suitability | Show distance, turf and dirt fit only when populated and race relevant. Keep heavy-track fit conditional. Do not invent missing values. | Missingness: distance 32.18%, turf 31.66%, dirt 40.29%. CYB training grade has 100% missingness and is not displayed as evidence. |

## Redundancy and retained context

The policy hides 17 duplicate or mark representations from the **normal** Reader while retaining all source leaves in canonical storage. Hiding a mark or supplied rank changes presentation, not source availability. IDM and information index remain together because their provider roles are not proven identical. Stable index, CYB condition and CHA last clock remain available because their semantics are materially different from the dominant summary indices. All source records (KYI, CHA, CYB; BAC race context) remain represented. Stage B's SED outcomes are evaluation data only and must never enter a future Reader.

## Proposed evidence layout

```text
RACE CONTEXT (BAC)  surface, distance, class, field shape
RUNNER IDENTITY     horse and connection identifiers
ABILITY             IDM [primary]; information/longshot/JRDB class [supporting]
PACE / POSITION     late pace [primary]; front/pace/position numeric values;
                    projected mid -> last3f -> finish margins as one trajectory
TRAINING / CONDITION
                    KYI training [primary]; CHA last clock and CYB condition;
                    one shared CHA-total/CYB-training workout view; qualitative notes
SUITABILITY / CONNECTIONS
                    populated race-relevant fit; jockey index; stable context
DETAIL / PROVENANCE supplied ranks, orders, marks, raw workout, farm, source leaves
```

This is a layout proposal, not a prediction prompt. A renderer should preserve missingness, units, and source labels, and should make the detail/provenance block accessible on demand.

## Structural Reader example

The following is a **schema-only** example. Values are symbolic placeholders; it is not a race, result, or prediction.

```text
v0.4.6 catalog-shaped exposure for Runner A:
  ability: IDM=<idm>; total_index=<total>; info_index=<info>
  jockey: index=<jockey>; expected_top2=<top2>; mark=<jockey_mark>
  pace: late_index=<late>; late_rank=<late_rank>
  forecast_finish: order=<finish_order>; margin=<finish_margin>
  training: KYI_index=<kyi>; CHA_total=<cha_total>;
            CYB_training=<cyb_training>; CHA_last=<cha_last>; CYB_condition=<condition>

proposed 0.5.x normal view for the same source evidence:
  ABILITY: IDM=<idm>; supporting info=<info>
  PACE / POSITION: late=<late>; projected finish margin=<finish_margin>
  TRAINING / CONDITION: KYI=<kyi>; workout summary=<cyb_training>
                        [CHA total same observed representation];
                        CHA last=<cha_last>; CYB condition=<condition>
  CONNECTIONS: jockey index=<jockey>
  DETAIL / PROVENANCE: total=<total>; expected top2=<top2>;
                       jockey mark=<jockey_mark>; late rank=<late_rank>;
                       finish order=<finish_order>; CHA total=<cha_total>
```

For these 15 explicitly named scalar slots, the illustrative normal view has 9 slots: 6 duplicate/detail slots move out of normal presentation. The provenance block still has access to all 14. This is a **structural count**, not a measured byte or token reduction on an actual committed Reader example. For the complete catalog, 17/73 leaves (23.3%) are marked hidden from normal presentation; that is an upper-bound field-slot count, not a predicted token reduction. A later renderer benchmark must measure real serialized bytes/tokens before claiming savings.

## v0.4.6 to 0.5.x migration and compatibility

The JSON mapping enumerates all 73 catalogued leaves and distinguishes unchanged, prominence-only, presentation redundancy, hidden-from-normal, conditional-only and insufficient-coverage states. The normal view changes information prominence for three primary anchors and selected secondary context. Duplicate ranks, order fields, marks and the identified composite pairs move to detail. Suitability gains an explicit coverage gate. Source leaves, raw records and lineage stay stored; the 0.4.6 Reader and prediction cohort stay unchanged. A future candidate renderer must be separately implemented and compared on the same pre-race evidence.

## Risks and validation boundary

- Provider formula equivalence is unproven outside the observed sample. Retain source values and monitor for CHA/CYB divergence.
- Hiding supplied ranks can remove tie/rounding information; detail must remain accessible, especially where exact-match rates were below 100%.
- Final-popularity controls cannot establish independent betting value; leading Q1 win ROI was negative.
- Reduced suitability coverage can bias a universal layout. Render only populated, relevant fields.
- Symbolic example counts do not estimate real prompt reduction. Test rendering size and source-family retention on committed clean examples before 0.5.x promotion.

**Final Stage C decision: DESIGN_0_5_CANDIDATE.** Stage B supports a conservative presentation candidate with explicit provenance. Promotion requires separate clean-blind validation and an audit decision. Production impact of this Stage C artifact set is zero.

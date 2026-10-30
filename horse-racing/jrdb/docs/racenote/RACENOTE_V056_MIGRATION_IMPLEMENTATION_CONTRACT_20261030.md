# RaceNote v0.5.6 — migration contract and implementation work order (2026-10-30)

Status: **APPROVED DESIGN / NOT YET IMPLEMENTED OR CUT OVER**. This document is an implementation specification, not authorization to run new v0.5.6 BTDAY or alter existing v0.5.5 assets.

## Source precedence and scope

- Repository `yukki0113/GPT`, latest `main` is the implementation authority.
- Read `horse-racing/jrdb/README.md`, `.gpt/{CONTEXT,HANDOFF,WORKFLOW}.md`, `docs/racenote/README.md`, `RACENOTE_V055_R6_PIPELINE_CURRENT_RUNBOOK_20261030.md`, current source/schema/tests before editing.
- Existing `v055` source, workflows, roots, SHA, Frozen Prediction/Confidence, checkpoint/BTDAY sessions, and reproduction routes **must remain unchanged**.
- Do not merely rename `v055` → `v056`; add v056 contracts and tools, then test and finally switch new-run pointers.
- Horse selection / ◎○▲△☆ semantics inherited from v0.5.5 r6. Changed behavior: explicit independent Confidence reasoning and mode-specific newspaper prose.

## Version identity

- Public model version: `RaceNote-Human-Context-Reader-0.5.6-candidate`.
- New contract revision (proposed): `v056-prediction-confidence-audit-newspaper-v1`.
- Runtime paths and tool names should use `v056` / `racenote_v056_*` for new-run entrypoints, but **retain original v055 modules as stable dependencies where semantics are identical**; wrappers/adapters are preferable to copying entire stacks.
- New sessions must have exact v056 contract identity and independent destination paths (`.../v056/`); old session roots and source `.../v055/` stay historical only.
- Explicit mode `BTDAY` / `FORWARD`; do not infer from date alone.

## Shared forecast path

1. Sealed CLEAN BLIND source, complete model reader, all runners compared by LLM; no deterministic marks, confidence, explanations.
2. LLM authors Decision Core, marks, and `prediction_audit_comment` for **both modes**. The comment summarizes why ◎ is prioritized, comparisons to ○/▲ and key risks. It is authored before Prediction Freeze, and must **not** contain an unfrozen Confidence grade.
3. Immutable Prediction Freeze committed to `main` with source and record SHA verification.
4. After successful persisted Prediction Freeze, LLM independently reviews frozen ◎ (cannot change marks) and authors grade A/B/C/Z and `confidence_review` for both modes.
5. Immutable Confidence Freeze committed to `main`. Results, payouts, target-day market data remain inaccessible until all relevant freeze/cohort gates are satisfied.
6. BTDAY: **skip all newspaper authoring**, then only after unlock do post-freeze evaluation.
7. FORWARD: after *all target races* Prediction + Confidence are frozen, separately produce `forward_newspaper_comment` from sealed pre-race RaceNote, frozen Decision Core, `prediction_audit_comment` and `confidence_review`. This is editorial post-processing, not another prediction. Never open results or target-day market data to write it. Publication gate checks correctness and rendering.

## Confidence decision policy

Confidence means likelihood judgment of ◎ finishing **first**, not confidence in winning a ticket / in-the-money:
- A: clear positive first-place case and comparative advantage over strongest rivals, no major unresolved defeating risk.
- B: ◎ reasonably most likely but live rival reversal/conditional uncertainty persists.
- C: ◎ top candidate yet winning scenario materially fragile or uncertain.
- Z: prior mandatory excluded/special-race classification, preserving existing exact applicability.

For each grade require structured `confidence_review`:
- `winning_case`: specific positive ◎ first-place evidence.
- `primary_rival`: strongest realistic rival (reference an actual frozen runner).
- `relative_advantage`: why ◎ is ahead, or limits of that advantage.
- `main_defeat_scenario`: main plausible loss mechanism.
- `risk_assessment`: why that risk is acceptable/limiting.
- `final_grade_reason`: reason for the exact A/B/C grade.

Z uses explicit non-applicability reason; don't invent win-case fields. Require semantic review by LLM and structural/data-source verification by code. Avoid fixed A quotas, numeric scores, keyword-only auto-grading or treating any risk as automatic downgrade.

## Records and validation

- Preserve existing Decision Core fields, `honmei_win.evidence`, `main_risk`, `candidate_selection.boundary_reason`, full evidence/provenance and auditability.
- `prediction_audit_comment` is mandatory in both BTday and forward prediction records; internal names, numbers, abbreviations are permitted, but it must be race-specific and consistent with Decision Core.
- `confidence_review` mandatory in both modes, stored alongside confidence grade in separately frozen confidence record.
- `forward_newspaper_comment` is **FORWARD-only**, generated *after both freezes*, separate derived artifact with immutable source SHA references, without changing Prediction/Confidence hash. Never require or generate it in BTDAY.
- Never make the forward editorial field mandatory in the prediction input/schema, or create an empty placeholder to satisfy validation.
- Separate strict gates: prediction structure/roster/mark/evidence; frozen honmei vs confidence/structured review; newspaper text fact/runner/mark agreement, forbidden internal strings, reproducible source linkage, PWA display. Automatic validators may reject inconsistencies but never generate or rewrite LLM judgments.
- Reader-facing v055 `reader_facing_reason` constraints cannot simply be imposed on audit commentary. Define new schema rules and backward-compatible display adapter from final v056 newspaper output, with version-specific validation.
- Maintain fail-closed UTF-8 / JSON / exact race roster / duplicate prevention / SHA / immutable write protections.

## Implementation work breakdown (do in code, not docs-only)

1. Inventory all `v055` references in `src/`, `schema/`, `config/`, `.github/workflows/`, `docs/racenote/`, `.gpt/`; classify as active new-run reference vs immutable reproduction history. Record inventory and migration map.
2. Create version-specific schema + validators with tests for both modes; use existing v055 modules where unchanged. Add v056 session builder/reader adapter as needed. No copying large unrelated JRDB code.
3. Add v056 prediction save/Freeze and separate v056 confidence save/Freeze plus checkpoints, submit gates, and two-phase orchestration. Preserve actual commits / verify on `main`, don't declare success from a workflow trigger alone.
4. Add independent v056 forward editorial tool with input manifest references to sealed pre-race RaceNote and *both* Frozen records; no target results/market input; enforce complete all-races freeze before prose generation; separate editorial publication SHA/manifest and QA.
5. Create v056 workflow entrypoints (explicitly name v056), T1 day-select/ZIP delivery where needed, T2 pipeline and T2_ONLY, BTDAY and forward runbooks. Restrict existing v055 flows to legacy sessions. Do not enable NEXT prematurely; ensure no cross-generation T1/T2 mismatch.
6. Update *active* `racenote_forecast_logic_current.json` prospective candidate pointer, new-run docs index/README/CONTEXT/HANDOFF/WORKFLOW and PWA downstream references **only after** new entrypoints and E2E pass. Historical text/pointers inside immutable artifacts stay v055.
7. Run focused tests: positive BTDAY 36R two freezes without newspaper; positive FORWARD two freezes then separate editorial; invalid race/missing comments, wrong honmei, A without review, contradictory review, Z applicability, mixed versions, attempted newspaper before freeze, market/result leakage, duplicate freeze, restart/interruption, PWA compatibility. Report exact executed commands, PASS/FAIL, commit SHAs and limitations.
8. Prepare new-run activation PR with rollback; cutover approval only after tests. Do not convert old `v055` sessions or historical A112R into `v056`.

## Operational cutover/rollback gates

Until implementation + positive end-to-end checks succeed:
- `v0.5.6` status = design only, and **current v055 r6 PIPELINE remains the operational runbook**.
- Do not point new BTdays to v056, do not modify current pointer, and do not rename/deprecate live workflows.
- Rollback = disable v056 new-run entrypoints / revert only active pointer and active docs. Frozen v056 and v055 artifacts are immutable; do not delete or overwrite them.
- Review outcome must include exact BTDAY and forward evidence; if forward environment cannot be tested, keep forward activation gated.

## Research comparison

Preserve A112R immutable v055 evaluation for comparison; fresh v056 clean-blind cohort only, with no result-tuned retroactive regrading. Evaluate A/B/C win-rate order, class distribution, sample sizes/CIs, A–B/B–C differences, contradictions and audit coverage. No arbitrary quota for A.

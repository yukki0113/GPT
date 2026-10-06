# JRDB Feature Audit — Stage C Resume Instruction

Status: **READY FOR EXECUTION**  
Date: 2026-10-06  
Purpose: resume Stage C after Codex cloud chat loss  
Canonical base: main after PR #1805 merge  
Required base commit: `2a71e2e9ccc9f4b728cfe9066ddcf32cd5761182`

## Context

The prior Codex cloud chat disappeared after Stage C had been requested.

Do **not** assume any uncommitted Stage C workspace state still exists.

Do **not** try to reconstruct hidden chat context.

Resume from repository state only.

The Stage B artifact-ingest PR #1805 has now been merged into main. The Stage B
pipeline, report and machine-readable results are canonical repository assets.

## Canonical inputs

Read these first:

1. `docs/racenote/research-work/README.md`
2. `docs/racenote/research-work/instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_C_INSTRUCTION.md`
3. `docs/racenote/research-work/audits/20261005_JRDB_FEATURE_AUDIT_STAGE_B_AUDIT.md`
4. `docs/racenote/research-work/reports/20261005_JRDB_FEATURE_AUDIT_STAGE_B_REPORT.md`
5. `docs/racenote/research-work/results/stage_b_2023_2025/ARTIFACT_MANIFEST.md`
6. machine-readable Stage B files under
   `docs/racenote/research-work/results/stage_b_2023_2025/`

Treat the existing Stage C instruction as authoritative. This resume instruction
only defines recovery procedure and commit discipline.

## Recovery rule

Before doing new Stage C work:

- inspect current repository and current branch;
- search for any existing committed Stage C artifacts;
- if committed Stage C artifacts already exist and are consistent with the
  canonical instruction, continue from them;
- otherwise start Stage C cleanly from the merged main state.

Do not rely on local-only files unless they are explicitly inspected and
proven to belong to the current canonical base.

Do not reuse stale outputs from an unknown pre-merge workspace.

## Stage C task

Execute:

`docs/racenote/research-work/instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_C_INSTRUCTION.md`

The intended outcome remains an information-architecture proposal for a future
RaceNote 0.5.x Reader.

Do not modify the active v0.4.6 Reader or production prediction behavior.

Do not create fixed numerical weights.

Do not extend Stage B to five years.

## Required deliverables

At minimum create and commit:

### 1. Stage C report

`docs/racenote/research-work/reports/20261006_JRDB_FEATURE_AUDIT_STAGE_C_REPORT.md`

The report must include:

- field-family decisions;
- redundancy decisions;
- proposed Reader tiers;
- concrete future Reader evidence layout;
- current-v0.4.6 -> proposed-0.5.x mapping summary;
- expected information/token reduction;
- risks and retained context;
- final Stage C decision:
  - DESIGN_0_5_CANDIDATE
  - KEEP_0_4_READER
  - NEED_TARGETED_RESEARCH

### 2. Machine-readable Reader policy

Create under:

`docs/racenote/research-work/results/stage_c/`

Preferred filename:

`reader_feature_policy_v0_5_candidate.json`

Each entry should include at least:

- feature_id
- current_v046_state
- proposed_tier
- display_group
- primary_representation
- retained_for_provenance
- change_type
- rationale
- evidence_reference

### 3. v0.4.6 -> 0.5.x mapping

Create a machine-readable mapping under the same Stage C results directory.

Preferred filename:

`v046_to_v05_reader_mapping.json`

Explicitly distinguish:

- unchanged
- prominence_only
- presentation_redundancy_only
- hidden_from_normal_reader
- conditional_only
- insufficient_coverage

### 4. Structural Reader example

Provide at least one concrete transformed Reader example or structural
simulation showing how the same evidence would be presented under the proposed
0.5.x policy.

Do **not** re-predict the race.

Do **not** inspect race results.

If practical, record:

- before/after byte count;
- before/after field count;
- duplicate representations removed;
- source families retained.

## Commit discipline

This recovery task must not end with workspace-only artifacts.

Before reporting completion:

1. ensure every required Stage C deliverable is committed;
2. ensure no unrelated files are included;
3. push the branch;
4. open a PR against main;
5. return:
   - commit SHA;
   - PR number / URL;
   - final Stage C decision;
   - brief list of produced files.

If GitHub write/PR creation is blocked, do not claim completion.

In that case, package all deliverables into a single artifact ZIP and explicitly
report that repository commit was not completed.

## Acceptance boundary

The task is not complete merely because analysis text was produced in chat.

Completion requires durable repository artifacts or, if write is impossible,
a clearly identified recovery ZIP.

Production impact must remain zero.

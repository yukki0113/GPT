# RaceNote Research Work Hub

Status: **ACTIVE SHARED HANDOFF AREA**  
Created: 2026-10-05

This directory is the canonical handoff area for substantial RaceNote research work that moves between ChatGPT/Codex/other execution threads.

The goal is to avoid copying long instructions and audit results through chat by hand.

## 1. Directory roles

```text
research-work/
├─ README.md
├─ instructions/   # work orders / research instructions
├─ reports/        # implementation or analysis results from the execution side
└─ audits/         # review / acceptance / next-stage decisions
```

### instructions/

Authoritative work instructions.

Each instruction should state:

- objective;
- scope;
- inputs and canonical sources;
- non-goals;
- leakage / clean-blind constraints when relevant;
- required deliverables;
- acceptance criteria;
- explicit stop conditions.

### reports/

Execution-side result reports.

Reports should record:

- what was actually done;
- repository changes / modules used;
- data periods and sample sizes;
- generated artifacts;
- checks/tests run;
- known limitations;
- deviations from the instruction;
- commit SHA(s) when applicable.

Do not rewrite the instruction as a report. Record actual work and evidence.

### audits/

Independent review of a report and its artifacts.

An audit should conclude with one of:

- ACCEPT;
- ACCEPT_WITH_NOTES;
- REVISE;
- STOP.

It should also state the next canonical instruction, if any.

## 2. File naming

Use:

`YYYYMMDD_<topic>_<stage>_<type>.md`

Examples:

- `instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_A_INSTRUCTION.md`
- `reports/20261006_JRDB_FEATURE_AUDIT_STAGE_A_REPORT.md`
- `audits/20261006_JRDB_FEATURE_AUDIT_STAGE_A_AUDIT.md`

Do not overwrite historical reports/audits when a new attempt is made. Add a new dated file.

## 3. Current research lane

Current project:

**RaceNote 0.5.x candidate research — JRDB Feature Audit**

The active RaceNote prospective prediction cohort remains:

`RaceNote-Human-Context-Reader-0.4.6-candidate`

The 0.5.x feature research runs in parallel and must not modify active v0.4.6 Reader exposure or horse-selection semantics until an explicit promotion decision is recorded in an audit.


## 3.1 Current stage

Stage A: **ACCEPT_WITH_NOTES**

Stage B (2023-2025): **ACCEPT**

Stage B decision:

`PROCEED_STAGE_C`

No five-year Stage B2 extension is requested.

Canonical Stage B report:
`reports/20261005_JRDB_FEATURE_AUDIT_STAGE_B_REPORT.md`

Canonical Stage B audit:
`audits/20261005_JRDB_FEATURE_AUDIT_STAGE_B_AUDIT.md`

Supplied artifact checksum manifest:
`results/stage_b_2023_2025/ARTIFACT_MANIFEST.md`

Current instruction:
`instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_C_INSTRUCTION.md`

The active v0.4.6 Reader / prediction cohort remains unchanged. Stage C is an
information-architecture proposal only.


## 4. Historical analysis horizon

The feature audit must not start with all available historical years.

### Primary window

Use **2023-01-01 through 2025-12-31** first.

Purpose:

- emphasize recent JRDB/JRA behavior;
- reduce long-horizon regime drift;
- keep execution and interpretation manageable;
- preserve 2026 as the current clean-blind/prospective research pool rather than exploratory feature-selection data.

### Extension window

Extend backward only if the 2023-2025 result is inconclusive because of sample size, instability, or weak separation.

Second window:

**2021-01-01 through 2025-12-31**

The five-year analysis must be treated as an extension/sensitivity check, not silently merged into the original result.

### Stop condition

If the five-year result still does not show stable, practically useful feature behavior, do not keep widening the period in search of a signal.

Record the outcome as:

> No sufficiently stable feature-level prioritization was established beyond the current Human-Context approach.

In that case, retain the 0.4.x principle: let the model interpret the complete evidence context without adding a new fixed JRDB feature hierarchy.

## 5. What counts as useful evidence

A feature is not useful merely because a higher value has a higher raw win rate.

The audit should distinguish:

- predictive strength;
- monotonicity;
- year-to-year stability;
- market independence / whether the signal is already fully priced;
- redundancy with other JRDB features;
- conditional usefulness by broad race context;
- sample size.

Do not jump directly to fixed numeric weights.

Any later 0.5.x proposal should prefer information-priority tiers or Reader exposure changes over a new hand-built composite score unless the research clearly justifies otherwise.

## 6. Stage structure

Planned sequence:

### Stage A — Feature Inventory

Inventory JRDB / PACI / Analysis / RaceNote / Reader fields and lineage.

No performance tuning.

### Stage B — 3-Year Historical Feature Audit

Analyze 2023-2025.

Required baseline views include overall + year-by-year stability.

### Stage B2 — Optional 5-Year Extension

Only if Stage B audit concludes that more sample is genuinely needed.

Analyze 2021-2025 with explicit comparison to the 3-year result.

### Stage C — Redundancy / Reader Recommendation

Only after an accepted Stage B/B2 result.

Produce evidence-backed candidates such as:

- KEEP_A;
- KEEP_B;
- CONTEXT_ONLY;
- REDUNDANT;
- LOW_SIGNAL;
- HIDE_CANDIDATE.

Stage C is still a recommendation stage. It does not automatically modify the active Reader.

## 7. Working rule

When a chat or Codex thread needs to hand work to another thread:

1. create or update the relevant instruction/report/audit file here;
2. refer to that file path in chat;
3. do not require the user to paste the full content manually;
4. preserve the file as the canonical record of the handoff.


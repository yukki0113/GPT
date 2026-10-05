# EdgeDB v0.4 — ChatGPT / Codex Collaboration Workspace

Status: ACTIVE  
Scope: JRDB EdgeDB v0.4 research / SHADOW only  
Production impact: NONE

## Purpose

This directory is the shared Git handoff area between ChatGPT and Codex for EdgeDB v0.4 research and development.

Use it to avoid copying long instructions/results through chat. Both sides should read the latest relevant document here before continuing work.

## Structure

- `instructions/` — task instructions, research requests, audit requests, implementation requests
- `results/` — execution results, audit reports, findings, completion notes

## Naming

Use:

`YYYYMMDD_<sequence>_<short-topic>_<type>.md`

Examples:

- `20261005_001_stage-c1-audit_instruction.md`
- `20261005_001_stage-c1-audit_result.md`

Keep the same date / sequence / topic between an instruction and its corresponding result when practical.

## Status

Every instruction/result document should state one of:

- `TODO`
- `IN_PROGRESS`
- `DONE`
- `BLOCKED`

For `BLOCKED`, record the blocker and the exact next action required.

## Handoff contract

1. Git documents in this workspace are the canonical handoff record between ChatGPT and Codex.
2. Do not rely on chat-only context for decisions that materially affect the next worker; write those decisions here.
3. Result documents must record inputs, work performed, outputs, validation, unresolved issues, and relevant commit/artifact identifiers.
4. A result must not silently redefine the instruction. Deviations must be explicit.
5. Prefer append/new-document handoffs over rewriting historical instruction/result records.

## EdgeDB v0.4 safety boundary

- v0.4 remains a research / SHADOW lane unless an explicit separate production promotion decision is made.
- Do not change v0.2 STANDARD or v0.3 SHADOW semantics as a side effect of work recorded here.
- Keep Performance and Value lanes distinct.
- Popularity / odds must not enter candidate generation; they are evaluation-only unless the canonical v0.4 design is formally revised.
- Production changes and research experiments must never be mixed in one implicit step.

Canonical design reference:

`horse-racing/jrdb/docs/EdgeDB_v0_4_HighOrder_Transition_Value_Discovery_Design_20260926.md`

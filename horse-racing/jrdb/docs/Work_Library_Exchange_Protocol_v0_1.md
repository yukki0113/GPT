# JRDB Work / Library Exchange Protocol v0.1

## 1. Purpose

This protocol defines how the JRDB PWA independent-index project is split between:

- **Controller thread**: design decisions, methodological governance, adoption/rejection decisions, prioritization
- **ChatGPT Work thread**: implementation, tests, Git updates, GitHub Actions execution, real-data audits, artifact production
- **GitHub main**: canonical source for code, schemas, durable design docs, workflows, and accepted implementation state
- **ChatGPT File Library**: cross-thread transport for work requests, result summaries, manifests, and other handoff artifacts

The purpose is to avoid relying on conversation-only context when moving between the Controller thread and Work.

## 2. Canonical-source rule

Before implementation, Work must always fetch the latest `main` and read the relevant canonical documents. Conversation summaries are orientation only.

Primary repository:

```text
yukki0113/GPT
```

JRDB root:

```text
horse-racing/jrdb/
```

At minimum, for independent-index work read:

```text
horse-racing/jrdb/README.md
horse-racing/jrdb/docs/JRDB_PWA_Index_Design_v0_1.md
horse-racing/jrdb/docs/JRDB_PWA_Index_Feature_Registry_v0_1.md
horse-racing/jrdb/docs/RunPerf_v0_1.md
horse-racing/jrdb/docs/Work_Library_Exchange_Protocol_v0_1.md
```

For a task-specific area, also read its schema, builder, audit, tests, and README before changing it.

## 3. Library message model

### 3.1 Controller -> Work

The Controller issues exactly one work package using:

```text
JRDB_Work_INBOX_<YYYYMMDD>_<NNN>.md
```

Example:

```text
JRDB_Work_INBOX_20260901_001.md
```

The file must contain a stable `request_id`:

```text
request_id: JRDB-WORK-20260901-001
```

Work must search the File Library for the exact request ID / filename before starting.

### 3.2 Work -> Controller

Work must return a result package using:

```text
JRDB_Work_OUTBOX_<YYYYMMDD>_<NNN>.md
```

with the same `request_id`.

If additional files are produced, Work also creates:

```text
JRDB_Work_ARTIFACTS_<YYYYMMDD>_<NNN>.md
```

The manifest lists each artifact filename, purpose, provenance, checksum when relevant, GitHub Issue/run/artifact IDs when relevant, and whether the artifact is canonical or disposable.

### 3.3 File Library as transport, not canonical implementation source

Library handoff files are transport records. They do not supersede GitHub main.

Accepted code/schema/workflow/design changes must exist on GitHub main. Large generated databases or raw JRDB ZIPs remain outside Git unless explicitly approved.

## 4. Required INBOX fields

Every INBOX should contain:

```text
request_id
issued_at
controller_role
work_role
objective
starting_state
canonical_files_to_read
required_tasks
acceptance_gates
hard_constraints
allowed_autonomous_decisions
controller_decisions_required
required_outbox_filename
```

If a prior OUTBOX is relevant, its filename/request ID must be referenced explicitly.

## 5. Required OUTBOX fields

Every Work completion or block must create an OUTBOX. Chat-only reporting is insufficient.

Required fields:

```text
request_id
status: COMPLETE | PARTIAL | BLOCKED | FAILED
started_from_git_sha
finished_at_git_sha
commits
files_created
files_updated
files_deleted
tests_run
test_results
workflows_or_issues
real_data_audits
artifacts
acceptance_gate_results
methodological_changes
assumptions
unresolved_items
controller_decisions_requested
recommended_next_work_package
```

`methodological_changes` must be `none` unless Work had explicit authority to change methodology.

## 6. Blocked / failed work

If Work cannot complete a task, it must still create the OUTBOX.

Do not replace missing evidence with guesses. Record:

- exact failing command / workflow / step
- observed error
- Git SHA used
- relevant file / log / Issue / run / artifact ID
- what was attempted
- what remains unknown
- safest next action

A technical failure must not be misreported as a model/data failure, and a model failure must not be hidden by a technically successful workflow.

## 7. Work autonomy

Work may autonomously:

- implement the requested frozen specification
- add tests and audit guards
- refactor implementation when behavior is unchanged
- fix clear parser/schema/workflow defects with evidence
- add performance improvements that do not alter model semantics
- run GitHub Actions and real-history audits
- add status / operation documentation for implemented behavior

Work must stop and request Controller judgment before:

- changing a frozen model specification
- opening a reserved evaluation period earlier than instructed
- changing feature meaning or availability timing
- adding odds/popularity to Ability or Edge
- changing adoption/rejection criteria after evaluation results are known
- silently imputing structural missing data
- replacing a failed method with a new model and treating the old holdout as untouched

## 8. Temporal / leakage rules

All work must preserve as-of chronology.

- no current race result as prediction input
- no same-day future race result as historical input
- no later-year coefficient backfill into earlier rows unless an explicitly documented retrospective warm-up rule permits it
- odds/popularity remain outside RunPerf, Ability, and Edge
- published snapshots are immutable; live adjustments are separate

## 9. Code and implementation style

For project code:

- readability over compression
- explicit type annotations where practical
- avoid conditional-expression / ternary style
- functions/methods have docstrings or equivalent documentation
- nontrivial processing blocks have comments explaining intent
- fail closed on ambiguous keys / revisions / availability
- missing is not silently converted to neutral zero
- final derived scores retain transparent components and provenance

## 10. Controller receipt procedure

When the user asks the Controller thread to continue after Work completes, the Controller should:

1. search File Library for the exact OUTBOX request ID or filename
2. open the OUTBOX and artifact manifest if present
3. verify the referenced Git main state independently for material decisions
4. make methodological/adoption decisions in the Controller thread
5. issue the next numbered INBOX if more implementation is required

Do not ask the user to manually copy Work's prose back into the Controller if an OUTBOX exists in Library.

## 11. Naming / sequencing

Use one monotonically increasing work package number per day.

```text
..._001
..._002
..._003
```

Never overwrite an earlier INBOX or OUTBOX. Corrections use a new package number and reference the superseded request ID.

## 12. Scope of v0.1

This protocol begins at the transition from official RunPerf v0.1 to official RunPerf materialization and Ability implementation.

Canonical RunPerf specification:

```text
T1|EXPANDING|RAW
```

RunPerf-level 2024-2025 holdout has already been consumed and passed `PASS_STRONG`. This does not authorize Work to use 2024-2025 freely for Ability model tuning. Ability development-period governance remains a Controller decision; until instructed otherwise, Work should build infrastructure and restrict model-selection/tuning work to the established development period.
# RaceNote v0.5.4 Candidate — Single-Day Research Runbook

Status: **PROMOTED CURRENT / NEW v0.5.4 SESSIONS**
Contract: `FORECAST_HUMAN_CONTEXT_READER_v0_5_4_CANDIDATE.md`
Logic: `RaceNote-Human-Context-Reader-0.5.4-candidate`
Revision: `v054-authored-prose-r3` (legacy r2/r1 Freeze verification remains supported)

## Scope and non-negotiable boundary

This path forks the existing 0.5.3 r2 single-day session into a separate
`v054/` operation directory. Do not reuse a 0.5.3 session/frozen-record file,
and do not settle or revise any v0.5.3 Freeze in the new path.

- Prediction requires market-blind, pre-result `forecast_prep`.
- The preparer must use **canonical RRDB v0.5 enrichment**:
  `racenote_rrdb_enrichment.py` / `jrdb_recommendation_signals.py`.
- Source-race SRB is read from the immutable shared `race_lap.parquet`
  **only through `RaceLapReader`**.
- KYI must come from a verified pre-race or historical canonical KYI archive.
  The neutral bundle builder extracts allowlisted KYI fields, not today's
  final odds, result or popularity.
- Every source-run SRB row must have `race_date < prediction_date`.
- Missing KYI stays unavailable; an old RRDB v0.4 Recommendation never
  silently becomes a v0.5 signal. v0.5.4 session initialization requires
  full prepared RRDB v0.5 coverage; `NO_MATCH` is valid coverage.

## 1. Prepare the existing market-blind source

Reuse the v0.5.3 canonical 2026 PACI / historical Warehouse preparation
routing, after ensuring that the daily RRDB enrichment uses the **current
v0.5 contract** rather than an older archived recommendation artifact.

Expected inputs:

```text
<operation-root>/forecast_prep/day_prep_handoff.json
<operation-root>/forecast_prep/reader_stripped_manifest.json
<operation-root>/forecast_prep/reader/*.json
<verified-input-root>/KYI*.zip
<verified-lap-store>/race_lap.parquet
```

Require in `day_prep_handoff.json`:

```text
market_blind=true
stripped_at_input_bind=true
result_opened=false
target_market_opened=false
```

Use SHA-pinned materialized assets. The v0.5.4 path neither downloads nor
directly queries raw storage; it consumes already-reviewed local assets.

## 2. Build neutral KYI evidence

```bash
python horse-racing/jrdb/src/racenote_v054_kyi_bundle.py \
  --prep-root <operation-root>/forecast_prep \
  --kyi-archive <verified KYI-containing ZIP> \
  --output <operation-root>/v054_inputs/kyi_bundle.json
```

Additional verified KYI ZIPs can be specified by repeating
`--kyi-archive`. This command matches target runner by target-date KYI
member plus exact race number, blood registration number and horse number.
Unmatched KYI rows are reported as missing rather than guessed; duplicate
identities fail. `previous[]` preserves the two reference-run selectors.

The bundle records the required RRDB v0.5 contract but **does not compute
recommendations**: those must already be present in the canonical prepared
Reader. It also does not compute horse scores or public marks.

## 3. Initialize v0.5.4 sealed Reader

```bash
python horse-racing/jrdb/src/racenote_v054_single_day.py init \
  --prep-root <operation-root>/forecast_prep \
  --root <operation-root>/v054 \
  --base-main-sha <40-char exact source-main SHA> \
  --evidence-bundle <operation-root>/v054_inputs/kyi_bundle.json \
  --race-lap-parquet <verified-lap-store>/race_lap.parquet
```

Initialization writes `v054/session.json`, `reader_manifest.json`,
`reader/*.json`, and a snapshot of `input_evidence.json`.
It binds the KYI evidence snapshot and SRB Parquet SHA-256 to the session
identity. This prevents accidental mixing with another source generation.

The model-facing Reader distinguishes:
- standard DATA / TRENDS, RACEREVIEW and ABILITY;
- `rrdb_v05` as one versioned Recommendation object;
- `historical_race_lap_contexts` containing available historical shape,
  explicit `NO_LAPS`, `MISSING` and `AS_OF_EXCLUDED` states;
- `jrdb_hidden_value_context` with reference runs, longshot type/index and
  ticket-index disagreement, explicitly **no additive score**.

Only actual past-race source keys are looked up; SRB is not interpreted as a
horse sectional. New KYI reference details provide attention hints rather than
winning votes.

## 4. Author, checkpoint, Freeze and verify

For each race, the model authors a complete Decision Core (the same five-horse
structure, fixed challenger boundary and no rank score) after inspecting that
race's complete bound Reader.

Conversation state is not a source of truth. New v0.5.4 BTDAY runs keep
authoring/restart state in the operation directory so a long card can resume
without carrying all prior Reader content in chat context.

### 4.1 Neutral authoring workspace

After T1/session sealing, an optional neutral workspace index may be written
under `v054/` (for example `authoring_workspace.json`). It is navigation
support only.

Allowed content:
- selection/session identity and Reader manifest SHA;
- race identity and bound Reader path/SHA;
- runner number/name;
- coverage state;
- compact neutral projections of already-bound pre-race facts such as IDM,
  suitability, training, KYI, running style, forecast margins and RRDB coverage.

The workspace must explicitly state that it is **not sufficient evidence for
authoring**. Before authoring each race, the model still reads the complete
bound Reader.

Forbidden workspace content:
- marks or rank order;
- ordinary-five membership;
- external challenger or boundary horse/candidate;
- confidence;
- Decision Core text;
- reader-facing prose;
- deterministic recommendations or scores not already part of the Reader.

A helper may compress transport, but it may not narrow the prediction problem.

### 4.2 Model-authored chunks and progress checkpoints

Author in 3–4 race chunks by default, reading each Reader individually. Smaller
chunks are allowed when needed; the number is an operational recovery unit, not
a prediction feature.

Each completed model-authored chunk may be committed immediately. A
`T2_PROGRESS.json`-style file may record only operation state, for example:
- selection_id / session_id / Reader manifest binding;
- chunk race range;
- status such as `NOT_STARTED`, `AUTHORED`, `VALIDATED`;
- authored chunk path and SHA;
- next unresolved chunk.

The progress file does not contain a marks plan and must not reconstruct
Decision Core or prose. A new chat/thread resumes from the progress file plus
the referenced bound Reader/chunks. Completed chunks are not re-authored merely
because the conversation changed.
`reader_facing_reason` is authored **per race by the model**, using the already-authored Decision Core; it is not produced by a formatter or fallback template. It is a reader-facing editorial note, not a checklist summary. The model chooses the most useful race-specific point and is not required to cover ◎/○/▲ in a fixed order, mention every mark, or use a fixed sentence count.

**Do not put Decision Core or newspaper-prose construction code in a workflow.**
A workflow may only take model-authored venue JSON and run save / validation /
Freeze / verify. It must not maintain a marks plan and expand it into
`race_model`, `mainline_cases`, `ranking_reason` or
`reader_facing_reason`, and must not assemble prose with f-strings,
formatters or fixed sentence patterns. There is no programmatic prose fallback.

Each new-r2 core includes:

```json
"reader_facing_reason_authorship": {
  "mode": "MODEL_AUTHORED_PER_RACE",
  "programmatic_template": false,
  "basis": ["<the Decision Core field(s) actually used>"]
}
```

`basis` is non-empty but has no mandatory member in r3. Do not publish internal terms such as `ordinary five`, `sealed Reader`, contract/plumbing labels, or trivial mark enumeration.

### 4.3 Pre-Freeze execution preflight

Before invoking the first save / Freeze workflow for a new T2 card, the
execution owner must validate the current implementation contracts once
against latest `main`. This is an operational preflight, not prediction
reasoning.

Required checks:

1. Read the active v0.5.4 Decision Core validator and authoring quality guard:
   - `src/racenote_decision_core_v054.py`;
   - its inherited boundary/schema validators;
   - `src/racenote_v054_authoring_quality.py`.
2. Confirm the exact persisted schema before authoring is finalized. In
   particular:
   - `ADMIT_CHALLENGER`: `boundary_review.alternative_horse_no` is the
     **displaced ordinary boundary horse**;
   - `KEEP_ORDINARY_FIVE`: it is the **external challenger**;
   - `rrdb_refs` uses the active persisted RRDB reference schema and must not
     be replaced by an ad-hoc signal-description structure.
3. Confirm the deterministic quality conditions that will be applied at
   Freeze. The model must express genuine race-specific comparisons from the
   Reader; do not add unsupported keywords merely to satisfy the guard.
4. After all chunks are authored but **before the first Actions Freeze run**,
   run one full-card preflight over all Decision Cores using the same schema and
   quality rules as the production Freeze path. Resolve all violations while
   results remain unopened.
5. Only after the full-card preflight is clean should the execution owner run
   venue save -> Freeze -> verify.

The purpose is to prevent avoidable retry loops such as:

```text
author
  -> Actions
  -> schema FAIL
  -> edit
  -> Actions
  -> quality FAIL
  -> edit
  -> Actions again
```

The preferred path is:

```text
contract/schema preflight once
  -> 3-4R Reader authoring chunks + checkpoints
  -> full-card schema/quality preflight once
  -> one mechanical save / Freeze / verify run
```

### 4.4 Transport and retry efficiency

The complete bound Reader remains mandatory per race, but execution should
avoid redundant retrieval and polling.

- Resolve the Reader file list/manifest once per card.
- Fetch each race's complete Reader once for the authoring pass unless a
  specific validation failure requires reopening it.
- Do not repeatedly fetch alternate compact projections of the same Reader
  merely to rediscover its schema; schema belongs to the validator/preflight.
- Commit 3-4 race model-authored chunks as recovery checkpoints, but do not
  re-author completed chunks on a technical retry.
- When an Actions retry is necessary, inspect the failing step/log once,
  classify it as schema / quality / infrastructure, and correct only the
  affected pre-Freeze artifact or execution plumbing.
- Avoid tight repeated workflow polling; query at meaningful state
  transitions (queued -> running -> save -> Freeze/verify -> completed).
- A technical retry must preserve prediction meaning unless the pre-Freeze
  validator identifies a genuine Reader-grounded Decision Core defect.

These rules optimize execution time without relaxing clean-blind integrity,
complete-Reader authoring, or the v0.5.4 quality gate.
### 4.5 Save / Freeze / verify

```bash
python horse-racing/jrdb/src/racenote_v054_single_day.py save \
  --root <operation-root>/v054 \
  --decisions <model-authored-venue>.json

python horse-racing/jrdb/src/racenote_v054_single_day.py freeze \
  --root <operation-root>/v054

python horse-racing/jrdb/src/racenote_v054_single_day.py verify \
  --root <operation-root>/v054
```

Do not open target results before `verify` succeeds. The existing
boundary validator protects the five/◎○/▲ rules; the v0.5.4 guard additionally
rejects generic/internal newspaper prose.

### 4.6 Confidence Freeze and result-unlock barrier

For a prospective BTDAY that participates in confidence research, completing
the prediction Freeze is not yet permission to open results. Before result
acquisition, persist the pre-result confidence artifact (currently
`v054/confidence_pre_result.json`) bound to the frozen records SHA.

It records the confidence assignment and any separately defined prospective
A-purification/shadow fields while:
- `result_consulted=false`;
- `payout_consulted=false`;
- `target_market_consulted=false`.

The lifecycle is therefore:

```text
T1_SEALED
  -> AUTHORING_IN_PROGRESS
  -> AUTHORING_COMPLETE
  -> FROZEN
  -> FORMAT_AUDIT_COMPLETE
  -> CONFIDENCE_FROZEN
  -> RESULT_UNLOCKED
```

If confidence is not part of the active research contract, the explicit
confidence stage may be marked `NOT_APPLICABLE`; it must not be silently
skipped for a cohort that is evaluating confidence. Result opening is
fail-closed until the applicable pre-result artifact exists.

This is an operational transaction barrier, not a change to horse selection or
A/B/C semantics. Existing historical Freezes are not rewritten to add missing
confidence artifacts.
Validators cannot prove nuanced racing claims: inspect evidence fidelity
and unsupported specificity on representative samples.

## Authoring Quality Gate (new prospective Freeze; BTDAY-0104+)

For new `v054-authored-prose-r3` sessions, T2 authors in small recovery chunks (normally **3–4 races**), reading the complete Reader individually. Common helpers may manage transport
and validation but may **not construct marks, Decision Core, boundary comparison,
ranking reasons, or reader-facing prose**. Saving a complete venue JSON is
still permitted; the chunk limit applies to authoring, not the venue filename.

Before a new Freeze, `racenote_v054_single_day.py freeze` examines every authored Decision Core across the full day and writes `v054/authoring_quality_report.json`. Decision Core fields remain subject to race-specific evidence, boundary-comparison and ◎/○ ranking-specificity checks. Reader-facing prose is checked only for operational accidents: known generic/fallback language, internal plumbing language, trivial mark enumeration, implausible length, or day-wide near-duplicate reuse. The gate does **not** grade prose composition or require specific marks, comparison words, evidence tokens, sentence count, or a narrow character target. Only a PASS can be frozen; the frozen report is separately SHA-sealed and verified.

Mechanical keyword and similarity detection is a **necessary screen, not
proof of horse-specific evidence truth or model provenance**. The execution
owner must also inspect representative Reader-to-Core source alignment and
authoring provenance before formal acceptance. Do not manufacture evidence
tokens to pass the gate. Rare valid cases flagged by heuristics require
revision **before Freeze**, not bypassing the guard.

Legacy frozen assets remain immutable; this gate does not retroactively
invalidate old seals. BTDAY-0103 is `BLIND_INTEGRITY_OK`,
`AUTHORING_CONTRACT_INVALID`, and
`EXCLUDE_FROM_FORMAL_EVALUATION`; its existing Freeze must not be rewritten.
BTDAY-0102 remains a valid clean-blind sample subject to the existing audit.

## 5. Release gate

Before formally adopting v0.5.4, run the source parser + as-of tests, check
real generated v0.5.4 Reader completeness and duplication, inspect at least
representative venue files, and verify an entire new untouched day end-to-end.
Compare against v0.5.3 only in explicitly labeled retrospective diagnostic
or independent forward evaluation. Keep confidence A/B/C and BP2 unchanged
until their own prospective research protocols authorize changes.

The promoted current pointer references this v0.5.4 path. v0.5.3 remains available only for reproduction/audit of existing frozen assets.

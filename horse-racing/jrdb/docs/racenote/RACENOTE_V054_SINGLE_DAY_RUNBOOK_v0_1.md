# RaceNote v0.5.4 Candidate — Single-Day Research Runbook

Status: **CANDIDATE ONLY / NEW SESSIONS / NO PRODUCTION POINTER CHANGE**
Contract: `FORECAST_HUMAN_CONTEXT_READER_v0_5_4_CANDIDATE.md`
Logic: `RaceNote-Human-Context-Reader-0.5.4-candidate`
Revision: `v054-context-evidence-r1`

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

## 4. Author, save, Freeze and verify

For each race, the model authors a complete Decision Core (the same r2
five-horse structure, fixed challenger boundary and no rank score).
`reader_facing_reason` is now a supported 2–3 sentence explanation of
◎'s specific strength, ◎ versus ○ ordering and, when useful, ▲'s different
win route. Do not publish the internal terms `ordinary five`, `sealed Reader`,
`r2`, or trivial mark enumeration.

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
0.5.3 r2 validator still protects the five/◎○/▲ boundary rules; the
v0.5.4 guard additionally rejects generic/internal newspaper prose.
Validators cannot prove nuanced racing claims: inspect evidence fidelity
and unsupported specificity on representative samples.

## 5. Release gate

Before formally adopting v0.5.4, run the source parser + as-of tests, check
real generated v0.5.4 Reader completeness and duplication, inspect at least
representative venue files, and verify an entire new untouched day end-to-end.
Compare against v0.5.3 only in explicitly labeled retrospective diagnostic
or independent forward evaluation. Keep confidence A/B/C and BP2 unchanged
until their own prospective research protocols authorize changes.

This PR **does not** alter `racenote_forecast_logic_current.json` or
the v0.5.3 operation pointer.

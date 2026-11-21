# RaceNote Forward T1 — reusable producer acceptance and target binding

Status: **GENERATION-SET ORCHESTRATION CANDIDATE**

This directory owns the Git-side acceptance records used by RaceNote v0.5.6 FORWARD T1.
The safety boundary is unchanged: target-day result/market data is never accepted, producer CURRENT bytes remain SHA-pinned, and Prediction / Confidence stay separate immutable stages.

## Default flow

```text
post-race / pre-race producer operations
  -> exact CURRENT readback + producer evidence
  -> finalized SED consumed-field consistency check
  -> reusable generation-set acceptance
  -> target date request
  -> deterministic target binding to latest eligible generation set
  -> RaceNote v0.5.6 FORWARD T1
```

The complete acceptance record is no longer re-authored for every target date.

Records:

- producer evidence: `horse-racing/jrdb/forward-acceptance/producer-evidence/*.json`
- accepted generation set: `horse-racing/jrdb/forward-acceptance/generation-sets/*.json`
- target binding: `horse-racing/jrdb/forward-acceptance/targets/YYYYMMDD.json`
- legacy `racenote-forward-source-acceptance-v2` target records remain readable for reproduction/rollback.

## Producer evidence

Schema: `racenote-forward-producer-evidence-v1`. Top-level status must be `VERIFIED`.

Producer evidence is a reviewed committed declaration of exact producer outputs. It is not itself a T1 PASS. It includes:

- authoritative completed-race cutoff and immutable producer-operation reference;
- Analysis exact Drive source ID/SHA/archive format and producer acceptance reference;
- RRDB reviewed CURRENT file ID/ZIP SHA and producer acceptance reference;
- Course Fit SHA-pinned source parts, generation/as-of and producer acceptance reference;
- RaceLap exact Drive CURRENT ID/SHA and producer acceptance reference;
- finalized SED date/file-ID/SHA entries used for semantic consistency validation.

Do not create producer evidence from filenames, timestamps or guessed hashes.

## Producer acceptance workflow

Workflow: `.github/workflows/racenote_forward_acceptance_prepare.yml`

Issue Router entry: `[RACENOTE_FORWARD_ACCEPTANCE] <request-id>`

Issue body:

```json
{
  "producer_evidence_path": "horse-racing/jrdb/forward-acceptance/producer-evidence/<name>.json"
}
```

The workflow:

1. materializes the exact Analysis / Course Fit / RaceLap bytes named by producer evidence;
2. fetches the reviewed RRDB CURRENT;
3. materializes the pinned finalized SED sources;
4. runs `src/racenote_forward_consumed_field_check.py`;
5. measures actual generation IDs, manifest/content SHA and coverage;
6. writes one immutable reusable generation set under `generation-sets/`;
7. commits it to `main`.

A generation set is accepted only when finalized SED consumed-field validation is PASS. SED ZIP byte size, modified time, packaging or producer chronology alone are not failures.

## Consumed-field validation

The deterministic check compares canonical `jrdb_raw.py` interpretation of finalized SED with fields actually persisted/consumed by Analysis and RaceReviewDB.

For Analysis it checks direct SED-derived result fields such as finish, abnormal status, final odds/popularity and payout fields. For RRDB it checks the persisted race/horse result facts that originate from SED, including finish/time, pace/corner/lane and JRDB result metrics.

A semantic mismatch fails closed. The affected producer generation must then be rebuilt or reconciled. A ZIP SHA or timestamp difference by itself does not trigger a rebuild.

## Generation-set acceptance

Schema: `racenote-forward-generation-set-v1`.

A generation set has no target date. It binds:

- completed-race cutoff;
- Analysis generation / manifest / measured coverage;
- RRDB generation / manifest / ZIP / measured coverage;
- Course Fit generation / complete measured asset hashes / as-of;
- RaceLap generation / manifest / Parquet SHA / exact period_to;
- PASS consumed-field report SHA;
- exact source transport and producer provenance.

The same accepted generation set can therefore serve multiple future target dates until a newer completed-race generation set is accepted.

## Target binding

Schema: `racenote-forward-target-binding-v1`.

Target bindings live under `forward-acceptance/targets/YYYYMMDD.json`. `src/racenote_forward_target_binding.py` selects the unique latest eligible accepted generation set.

Eligibility requires:

- `required_completed_through < target_date`;
- Analysis/RRDB measured coverage covers the cutoff and remains before target;
- RaceLap `period_to` exactly equals the cutoff;
- Course Fit `as_of < target_date`;
- consumed-field consistency PASS.

If multiple different generation sets claim the same latest cutoff, selection fails as ambiguous. Selection never uses modified time or filename order.

## Single T1 request entry

Preferred Issue Router entry:

`[RACENOTE_FORWARD_T1] YYYYMMDD`

Minimal request body:

```json
{
  "target_date": "YYYY-MM-DD",
  "paci_drive_file_id": "TARGET_DATE_CANONICAL_PACI_FILE_ID",
  "paci_drive_sha256": "optional-known-64-hex"
}
```

`.github/workflows/racenote_v056_forward_paci_t1.yml` then:

1. verifies the canonical target PACI;
2. creates/reuses a target binding from the latest accepted generation set when no explicit legacy/v2 contract is supplied;
3. derives the RaceLap cutoff from the binding;
4. materializes and validates the bound source bytes;
5. runs the existing v0.5.6 CLEAN BLIND T1;
6. commits the immutable `v056_day` output and authoring bundle.

The previous `[RACENOTE_V056_FORWARD_PACI_T1]` route and explicit legacy v1/v2 inputs remain supported for reproduction and rollback.

## Fail-closed boundaries

- PACI remains canonical Drive only; no JRDB fallback from T1.
- A successful Data Storage run alone is not producer acceptance.
- CURRENT timestamps do not prove scientific freshness.
- Target/future results cannot enter a target binding.
- Semantic finalized-SED mismatch is never ignored.
- Unknown/ambiguous generation sets fail closed.
- T1 creates no automated marks or Confidence.
- Prediction and Confidence Freeze remain separate and immutable.
- Target results, target market and final odds remain closed before the pre-result boundaries.

## Structured failure contract

Accepted records remain immutable and fail-closed. The producer-acceptance and
T1 workflows publish a `racenote-forward-failure-v1` JSON failure receipt on
failure, with `error_code`, `failed_stage`, `detail` and `retryable`.

- `DATA_INVALID`: deterministic semantic/contract inconsistency, including
  finalized SED consumed-field mismatches, ambiguous newest generations,
  or attempted mutation of an already-bound immutable target. A consumed-field
  mismatch writes `consumed_field_report.json` with the specific differences
  before failing. Never mark it PASS or silently regenerate/promote.
- `ORCHESTRATION_MISSING`: required producer evidence, finalized SED delivery,
  or an eligible accepted generation set has not yet been prepared. This is
  not proof of bad data and must not be reported as such.
- `EXECUTION_FAILED`: unclassified shell/network/runner failures; inspect the
  failing step and do not guess whether the input is invalid or simply missing.

Both domain codes exit nonzero and write the same deterministic JSON shape.
The existing A05/v2 explicit source paths remain supported. T1 prevalidates
the requested JST target window and immutable output destination **before**
creating a target binding, and resolves RRDB file identity through the accepted
generation set rather than reading it from the minimal target-binding JSON.

The CI workflow must execute `test_racenote_forward_acceptance_orchestrator.py`
alongside the existing v2 and A05 regressions. Merge success and unit-test
PASS do not themselves constitute a live pre-race forward acceptance.

## Main modules

- `src/racenote_forward_source_resolver.py`
- `src/racenote_forward_source_acceptance.py`
- `src/racenote_forward_consumed_field_check.py`
- `src/racenote_forward_generation_acceptance.py`
- `src/racenote_forward_target_binding.py`
- `src/racenote_v056_forward_turn1.py`
- `.github/workflows/racenote_forward_acceptance_prepare.yml`
- `.github/workflows/racenote_v056_forward_paci_t1.yml`

Focused regression:

- `tests/test_racenote_forward_source_v2.py`
- `tests/test_racenote_forward_acceptance_orchestrator.py`
- `tests/test_racenote_a05_forward_freshness.py`

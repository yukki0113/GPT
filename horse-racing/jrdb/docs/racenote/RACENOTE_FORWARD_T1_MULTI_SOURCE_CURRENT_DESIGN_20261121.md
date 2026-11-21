# RaceNote Forward T1 — multi-source CURRENT acceptance design

Date: 2026-11-21 (JST)
Status: **DESIGN PROPOSAL / NOT IMPLEMENTED / NO FORWARD AUTHORIZATION**
Scope: v0.5.6 forward PACI T1 input acquisition and verification; reusable boundary for future BRDB/JPDB.
Decision goal: preserve fail-closed correctness while removing unnecessary dependency on GitHub Actions Artifact IDs.

## 1. Background and verified existing behavior

Canonical implementation:
- `.github/workflows/racenote_v056_forward_paci_t1.yml` requires `analysis_artifact_id`, `analysis_generation_id`, `course_fit_artifact_id`, `race_lap_artifact_id`, `freshness_acceptance_json`. Workflow fetches three Actions artifact ZIPs via `gh api repos/.../actions/artifacts/{id}/zip`; RRDB is separately fetched from reviewed Drive CURRENT.
- `src/racenote_v056_forward_freshness.py` (A05) validates dedicated completion evidence, Analysis immutable generation manifest and all asset SHA, actual Analysis Parquet MAX(race_date)/COUNT, RRDB ZIP/manifest/generation, and the exact matching accepted receipt; however it additionally requires an Analysis Actions Artifact ID.
- `src/racenote_v056_forward_turn1.py` repeats the A05 preflight; the downstream handoff includes Analysis/RRDB freshness evidence and strict no-result/no-market gates.
- `src/jrdb_race_lap_forward_current.py` already checks manifest schema/status, expected cutoff, Parquet SHA and actual dataset date range. `src/jrdb_race_lap_current_resolver.py` can validate existing CURRENT; refresh requires explicitly supplied canonical SED, not implicit network discovery.
- `src/racenote_fetch_rrdb_current.py` binds a reviewed RRDB Drive source pointer to a content SHA/CRC/current manifest receipt.
- `config/racenote_racelap_forward_current_binding.json` points to a 2026-10-17 artifact generation; it must **not** be inferred to represent current 2026-11-21 data.
- `daily/20261115/v056_day/source_audit/forward_analysis_rrdb_freshness.json` records accepted Analysis/RRDB coverage through **2026-11-08** for the **2026-11-15 target**. It cannot be recycled as evidence that 2026-11-15 results have been ingested for 2026-11-21.
- User-reported successful Data Storage fallback updates are **not** by themselves proof that their generations, receipts and target-specific coverage are accepted by T1.

Root cause: **transport coupling** (Actions ID required) and **content trust** (correct artifact/provenance/freshness) are mixed. Relax the first, not the second.

## 2. Invariants (non-negotiable)

1. Target PACI comes from the confirmed canonical Google Drive PACI folder, exact target-date identity and content SHA/receipt. No direct JRDB fetch or fallback. Target event-day inputs must exist before T1; no race result, final market, or post-target evidence.
2. Authoritative completion cutoff `required_completed_through` comes from a successfully verified dedicated JRDB postrace operation (explicit date + source reference + verification time), **not** wall-clock `target_date-1`, highest filename date, or input-side claim.
3. Every required outcome-derived dataset must have `required_completed_through <= measured_coverage < target_date` and exact received generation ID, manifest SHA and content SHA; RaceLap retains its exact `expected_period_to` rule. Course Fit follows its own contract (valid historical as-of coverage, not necessarily identical end date).
4. A valid manifest *alone* is not sufficient acceptance. Verified bytes must match an **independent, dedicated producer-side accepted receipt** (run ID/immutable handoff, trusted Drive source identity, generation and SHA). Consumer must not self-authorize a generation merely because it computed its hash.
5. Mutating/current pointers must be resolved once, materialized once, pinned by byte digest and rechecked before T1. Reject pointer rotation during acquisition, cross-generation mixes, mismatch, unsafe ZIP entries, duplicate files, path traversal and unknown schemas.
6. Failure is visible and attributable; no silent old-generation fallback, guessing IDs or SHA, auto-rebuild from SED, suppressing missing optional-looking inputs, or early T1 partial commit.
7. Keep v0.5.6 predictions, separate Confidence Freeze, PACI/no-market CLEAN BLIND, session contract and existing 7-strategy research unchanged.

## 3. Target architecture

```text
dedicated data operations (Analysis / RRDB / CourseFit / RaceLap)
  -> accepted producer receipt + immutable generation/verified CURRENT
  -> source locator (Actions Artifact | verified Drive CURRENT | Data Storage handoff)
  -> materialize to isolated temporary root
  -> content validators (existing canonical Reader/manifest/Parquet validators)
  -> source identity + producer acceptance + cutoff cross-check (new common gate)
  -> sealed input lock / verified source audit
  -> existing v056 forward T1 mechanical prep
  -> immutable Prediction Freeze -> immutable Confidence Freeze
```

Transport adapter only obtains bytes and provenance. It **must not decide** whether bytes are scientifically or operationally acceptable. Validation and producer acceptance use the same contract regardless of transport.

## 4. Input modes and trust boundaries

Use explicit per-dataset `source_mode`:
- `actions_artifact`: retained legacy behavior (accepted run/artifact ID and canonical manifest checks).
- `drive_current`: approved named source/folder or reviewed source pointer; fetch exact Drive file via established connector/controlled fetcher; record file ID, name, size, content SHA, and source-pointer revision. Do not infer trust from file name.
- `data_storage_handoff`: immutable staged generation provided with an independently accepted producer receipt, origin reference and content hashes. This is a **new adapter**, not automatically supported by existing T1.
- Do not support arbitrary public URL or unreviewed local path as an accepted source. Local paths may be internal post-materialization inputs only.

Minimum accepted source set is per dataset, not global:
| Dataset | Existing path | New path / acceptance |
|---|---|---|
| PACI | canonical Drive PACI | unchanged; not broadened |
| Analysis | accepted Actions artifact | validated immutable Analysis CURRENT generation through Drive/Data Storage handoff, producer acceptance, all fact/metadata asset SHA, row/date reconciliation |
| RRDB | approved Drive CURRENT with fetch receipt | preserve current path; A05 receipt generalized to transport-neutral identity, still compare ZIP SHA/current/manifest and approved pointer |
| Course Fit | accepted Actions artifact | only if published CURRENT/handoff format has a verified schema, as-of boundary and independently accepted producer receipt; no assumed auto freshness |
| RaceLap | accepted Actions artifact | verified Drive CURRENT or accepted Data Storage fallback snapshot, existing RaceLap manifest+Parquet validator, **exact** result cutoff; do not assume GitHub's 2026-10-17 binding is latest |
| Future BRDB/JPDB | out of T1 scope | new adapters only after separate prediction-safe contract acceptance |

## 5. New source binding contract v2 (illustrative, not active)

One immutable `forward_source_lock.json` is created after *all* source checks pass. Its values are measured and cross-checked; no free-form user-provided SHA guessing:

```json
{
  "schema_version": "racenote-forward-source-lock-v2",
  "target_date": "YYYY-MM-DD",
  "completion_evidence": {
    "status": "PASS",
    "reference": "<dedicated-results-operation-ref>",
    "required_completed_through": "YYYY-MM-DD",
    "verified_at_utc": "<ISO8601 UTC>"
  },
  "inputs": {
    "analysis": {
      "source_mode": "data_storage_handoff",
      "source_ref": "<accepted producer/transport reference>",
      "producer_acceptance_ref": "<independently verified run/receipt>",
      "generation_id": "<measured ID>",
      "manifest_sha256": "<64-hex>",
      "content_digest": "<dataset hash or full asset manifest root>",
      "coverage_through": "YYYY-MM-DD"
    },
    "rrdb": {
      "source_mode": "drive_current",
      "source_ref": "<reviewed Drive file ID/source revision>",
      "producer_acceptance_ref": "<accepted operation receipt>",
      "generation_id": "<measured ID>",
      "manifest_sha256": "<64-hex>",
      "transport_sha256": "<64-hex>",
      "coverage_through": "YYYY-MM-DD"
    },
    "course_fit": {
      "source_mode": "actions_artifact",
      "source_ref": "<artifact ID + run>",
      "producer_acceptance_ref": "<accepted operation receipt>",
      "generation_id": "<measured ID>",
      "manifest_sha256": "<64-hex>",
      "as_of": "YYYY-MM-DD"
    },
    "race_lap": {
      "source_mode": "drive_current",
      "source_ref": "<verified CURRENT file ID>",
      "producer_acceptance_ref": "<accepted operation receipt>",
      "generation_id": "<measured ID>",
      "manifest_sha256": "<64-hex>",
      "parquet_sha256": "<64-hex>",
      "period_to": "YYYY-MM-DD"
    }
  },
  "status": "READY_FOR_T1"
}
```

Required in production schema: explicit dataset type; source mode; reviewed source identity; producer acceptance reference and verification status; transport hash where applicable; generation, schema/logic version, manifest digest, actual content digest/asset receipts, coverage/as-of; target; resolved UTC time; immutable lock SHA; and error evidence for rejection. Unknown fields/types and contradictory periods fail closed. Redact access tokens and secret URLs.

The JSON above is **shape illustration** with placeholders, not a usable acceptance document. Actual schema must include PACI as well and be versioned before implementation.

## 6. Acceptance and freshness contracts

### 6.1 Completion authority
`required_completed_through` must be independently established from completed-result ingestion evidence. For 2026-11-21, the desired latest official completed meeting date may be 2026-11-15, but it must be *verified*; do not assert by calendar alone. Every required dataset must cover this cutoff where its contract entails result freshness.

### 6.2 Analysis
Retain `jrdb_analysis_parquet_current.resolve_current`, full manifest/partition metadata SHA validation, actual Parquet max race_date and row count. Compare measured `generation_id`, `manifest_sha256`, `coverage_through` and all asset hashes to **dedicated producer acceptance**. Accept a transport-independent `source_ref`; `artifact_id` is required only for the Actions adapter.

### 6.3 RRDB
Retain reviewed Drive file identity, source-pointer rotation check, ZIP CRC/SHA, current/manifest consistency and A05 cutoff comparison. Generalized `rrdb` receipt must not weaken present approved-source or content rules.

### 6.4 RaceLap
Retain existing manifest-schema/logic/version, current status, Parquet SHA, row/date checks, `period_to == expected_period_to`, `period_to < target_date`. Identify `expected_period_to` from dedicated completion evidence, not manually guessed. Fetching verified existing CURRENT is allowed; updating it within T1 is not. If the independently accepted CURRENT is stale, fail with a named missing-generation error.

### 6.5 Course Fit
Inspect existing physical/course-fit schema and accepted as-of rules before enabling non-Actions mode. Course Fit may be an as-of-snapshot rather than a continuously updated race-result dataset. Verify that its model inputs and generation do not include target/future outcomes. A generic `MAX(race_date)` substitution is not valid unless that dataset's contract defines it.

### 6.6 Multiple source disagreement
If two independently accepted sources claim different immutable generations or cutoffs for the same target, **do not choose highest timestamp or latest filename**. Resolve the canonical producer acceptance and fail if ambiguity persists. No freshness inferred from mutable Drive timestamps alone.

## 7. Concrete implementation proposal

1. `src/racenote_forward_source_resolver.py` (new): read versioned source request, call approved materializer adapters, resolve observed identity/bytes, write immutable staged output and source receipts. No prediction logic.
2. `src/racenote_forward_source_acceptance.py` (new): verify dedicated completion evidence; per-source manifests; accepted producer receipts; exact cutoff/as-of; cross-source generation/target consistency; seal `forward_source_lock.json`.
3. Extend `src/racenote_v056_forward_freshness.py` with **backward-compatible A05 v1** and new v2 source bindings. Remove unconditional `analysis_artifact_id` requirement only for trusted non-Actions mode; do not skip any Analysis/RRDB measured hash/coverage checks. Reject mixed-mode argument ambiguity. Avoid acceptance JSON generated only by T1 from untrusted data.
4. Extend `src/racenote_v056_forward_turn1.py` to accept `--source-lock <path>` in v2 mode and verify the lock matches already staged real paths; preserve legacy arguments/mode for reproduction. Emit source lock SHA, source modes, accepted generations/cutoff in operation handoff/source audit.
5. Add explicit `source_mode` + `source_acceptance_ref` routing in `.github/workflows/racenote_v056_forward_paci_t1.yml`; only require IDs for Actions mode. Separate source acquisition from the original T1 execution. **Do not** simply mark Artifact inputs optional without adding a valid materializer and receipt validator.
6. Update schema, tests, runbook and deploy only after independent dry-run. Preserve GitHub commit/authoring Artifact output format and v056 LLM downstream behavior.
7. Do not change original A05 receipts or prior immutable Daily/BTDAY output.

## 8. Failure codes and diagnostics

- `PACI_NOT_VERIFIED`
- `PRODUCER_ACCEPTANCE_MISSING`
- `SOURCE_IDENTITY_MISMATCH`
- `SOURCE_POINTER_CHANGED`
- `MANIFEST_OR_CONTENT_SHA_MISMATCH`
- `SOURCE_GENERATION_AMBIGUOUS`
- `COVERAGE_NOT_LATEST_CONFIRMED`
- `TARGET_OR_FUTURE_LEAK`
- `COURSE_FIT_ASOF_UNVERIFIED`
- `RACELAP_CUTOFF_MISMATCH`
- `SOURCE_LOCK_MISMATCH`

Each error must state dataset, required cutoff, observed cutoff, generation, source mode, and missing **nonsecret** evidence. Never print credentials. Keep no partial publish on failure.

## 9. Tests and promotion gates

- Existing Actions-only T1 fixture remains byte/semantics compatible (except separately versioned optional v2 metadata).
- New Data Storage handoff for Analysis and verified Drive CURRENT for RaceLap passes **only** with independent acceptance and identical measured bytes.
- Tampered ZIP/Parquet/manifest; SHA mismatch; expired/missing acceptance; wrong target; pointer changed during fetch; duplicate ZIP entry; unknown schema; ambiguous generations; unverified Course Fit as-of; missing official cutoff; stale RRDB/Analysis/RaceLap; target-date leakage: all fail closed.
- A05 v1 and v2 cannot silently mix identities. Re-running a given source lock yields identical source audit digests and predictions stay blind.
- E2E controlled replay with 2026-11-15 already sealed fixture and accepted source identities, then real 2026-11-21 T1 before prediction Freeze; compare Reader coverage, PACI SHA, no market/result access, published artifacts and handoff.
- Independent test review on PR, rollout behind explicit `source_contract_version=v2` switch; rollback to existing v1 via separate mode. Do not overwrite v1 output.

## 10. 2026-11-21 operational checklist (not yet executed)

1. Confirm target-date PACI in canonical Drive.
2. Confirm official completed-results cutoff from dedicated results operation and verify the exact accepted generations/receipts from the latest Analysis, RRDB, Course Fit and RaceLap operations (including reported Data Storage fallback). Obtain actual native artifacts; old 2026-11-15 T1 receipt covers only 2026-11-08.
3. If accepted Actions artifact exists for each required source, current v1 path can run after verifying A05 exact references; no code change needed.
4. If no corresponding Actions artifact exists but independently accepted Drive/Data Storage CURRENT does, **do not forge an ID**; implement and test the v2 adapter/acceptance path before using it.
5. If producer acceptance or freshness cannot be verified, fail with explicit source-specific report; do not assert this is merely an artifact routing problem.
6. Only after T1 source lock PASS, run v0.5.6 Prediction Freeze and Confidence Freeze separately, with no target result/market input.

## 11. Scope boundary

This document is a design only: no GitHub Actions workflow modifications, no reader/prediction/Confidence logic changes, no CURRENT publication or re-promotion, no result ingestion, no T1 dispatch, no 2026-11-21 prediction. BRDB/JPDB are future adapters and require independent prediction-safe gate.

## Canonical references

- `.github/workflows/racenote_v056_forward_paci_t1.yml`
- `src/racenote_v056_forward_turn1.py`
- `src/racenote_v056_forward_freshness.py`
- `src/jrdb_analysis_parquet_current.py`
- `src/racenote_fetch_rrdb_current.py`
- `src/jrdb_race_lap_forward_current.py`
- `src/jrdb_race_lap_current_resolver.py`
- `docs/racenote/RACENOTE_A05_ANALYSIS_RRDB_FRESHNESS_GATE_20261102.md`
- `docs/racenote/RACENOTE_V056_FORWARD_PACI_RUNTIME_20261030.md`
- `daily/20261115/v056_day/source_audit/forward_analysis_rrdb_freshness.json`

# RaceNote T1 v2 — accepted CURRENT input handoff

Status: **V2 GATE MERGED / INPUT ACCEPTANCE REQUIRED / NO 2026-11-21 PRE-RACE PREDICTION**
Initial implementation: PR #2677 merged as `1ae39eb6049fc3fec44a7859a03f07b4b7f2fa8c`
Tracking PR: https://github.com/yukki0113/GPT/pull/2677

## Why

The legacy forward T1 requires three specific GitHub Actions Artifact IDs regardless of whether equivalent CURRENT data has already been accepted via dedicated Data Storage / Drive operations. This v2 route removes that transport-only requirement, **not** the requirements for target-date isolation, completed-race coverage, full content hashes, independently accepted producer evidence, and market-blind forecasts.

## Source of truth / trust boundary

Before dispatch, the dedicated data owner must create a reviewed and committed acceptance record in this directory named `YYYYMMDD.json`. It must be reviewed independently from the RaceNote T1 consumer and must identify the actual output of the dedicated producer operations. T1 **does not synthesize a PASS** from the fact that a ZIP exists or compute a self-approval. The acceptance file is pinned to the checked-out Git HEAD; local modifications are rejected.

The approved source file references for `analysis`, `course_fit`, and `race_lap` are public Google Drive file IDs for SHA-pinned archives. Analysis CURRENT is normally a `tar.xz`; Course Fit and RaceLap are ZIP. The accepted Course Fit v0.1 baseline is distributed as **two** SHA-pinned Drive ZIP parts, not a single archive; use `course_fit.source_parts` with the exact full file IDs and SHA of both parts. The materializer only merges identical duplicate member bytes (the known `READ_FIRST.txt`). Specify `archive_format=tar.xz` on Analysis, and `archive_format=zip` on the others. The canonical RaceLap Drive ZIP wraps the dataset in `current/` and may also include `resolver_receipt.json`; the materializer normalizes only this verified layout. `data_storage_handoff` names the *producer route*, not a license to read arbitrary local files: the accepted output must also be staged in that verified public Drive channel. The older `actions_artifact` mode remains available through v1.

RRDB remains under the existing, separately approved Drive CURRENT source contract and fetcher. PACI continues to come exclusively from the canonical Drive PACI folder with its independent receipt.

## Accepted source record

An accepted file uses the following **schema shape**, with literal values filled from independent producer receipts. **Do not copy the placeholders and set status=ACCEPTED.** The `required_completed_through` value is the latest completed result date established by the dedicated result operation, not the preceding calendar day.

```json
{
  "schema_version": "racenote-forward-source-acceptance-v2",
  "status": "ACCEPTED",
  "target_date": "YYYY-MM-DD",
  "completion_evidence": {
    "status": "PASS",
    "source": "DEDICATED_JRDB_RESULT_OPERATION",
    "reference": "verified-result-operation-reference",
    "verified_at_utc": "YYYY-MM-DDTHH:MM:SS+00:00",
    "required_completed_through": "YYYY-MM-DD"
  },
  "analysis": {
    "status": "ACCEPTED",
    "source_mode": "data_storage_handoff",
    "source_ref": "reviewed-Drive-ZIP-file-ID",
    "source_sha256": "64-lowercase-hex",
    "archive_format": "tar.xz",
    "producer_acceptance_ref": "independent-analysis-accepted-run",
    "generation_id": "observed-Analysis-generation",
    "manifest_sha256": "64-lowercase-hex",
    "coverage_through": "YYYY-MM-DD"
  },
  "rrdb": {
    "status": "ACCEPTED",
    "producer_acceptance_ref": "independent-RRDB-accepted-run",
    "generation_id": "observed-RRDB-generation",
    "manifest_sha256": "64-lowercase-hex",
    "coverage_through": "YYYY-MM-DD",
    "file_id": "reviewed-existing-RRDB-CURRENT-Drive-file-ID",
    "zip_sha256": "64-lowercase-hex"
  },
  "course_fit": {
    "status": "ACCEPTED",
    "source_mode": "drive_current",
    "source_ref": "reviewed-Drive-ZIP-file-ID",
    "source_parts": [
      {"source_ref": "reviewed-Drive-part1-file-ID", "source_sha256": "64-lowercase-hex", "archive_format": "zip"},
      {"source_ref": "reviewed-Drive-part2-file-ID", "source_sha256": "64-lowercase-hex", "archive_format": "zip"}
    ],
    "producer_acceptance_ref": "independent-coursefit-accepted-run",
    "generation_id": "observed-CourseFit-generation",
    "manifest_mode": "accepted_asset_manifest",
    "manifest_sha256": "sha256-of-canonical-assets-json",
    "as_of": "YYYY-MM-DD",
    "assets": {
      "fit/research/candidate_fit_view.parquet": "64-lowercase-hex"
    }
  },
  "race_lap": {
    "status": "ACCEPTED",
    "source_mode": "drive_current",
    "source_ref": "reviewed-Drive-ZIP-file-ID",
    "source_sha256": "64-lowercase-hex",
    "producer_acceptance_ref": "independent-RaceLap-accepted-run",
    "generation_id": "observed-RaceLap-generation",
    "manifest_sha256": "64-lowercase-hex",
    "parquet_sha256": "64-lowercase-hex",
    "period_to": "YYYY-MM-DD"
  }
}
```

The schema shape is illustrative rather than a valid record. Actual records must list **every** Course Fit file in `assets`; in `accepted_asset_manifest` mode, `manifest_sha256` is SHA-256 of UTF-8 `json.dumps(assets, sort_keys=True, separators=(',', ':'))`. If the published Course Fit ZIP contains a native validated `manifest.json`, set `manifest_mode=native` and pin that exact manifest digest instead.

For the v2 Drive materializer, Analysis ZIP contents must unpack to the canonical `current.json` and `generations/<generation>/...` layout; Course Fit's two ZIPs must jointly contain the approved complete file set; RaceLap ZIP must contain `race_lap.parquet` and `manifest.json` at its root. ZIPs with unsafe paths, symlinks, duplicate members, oversized unpacked data or mismatched SHA are rejected. The Analysis canonical resolver checks every underlying Parquet asset digest and actual MAX(race_date)/COUNT. RRDB uses the existing A05 manifest/ZIP validation, and RaceLap uses the canonical as-of/Parquet validator.

## Forward workflow invocation

Use workflow `.github/workflows/racenote_v056_forward_paci_t1.yml`.

In **v2 mode**, supply:
- `target_date`;
- `paci_drive_file_id` (optionally the independently known `paci_drive_sha256`);
- `race_lap_expected_period_to` equal to the separately verified result cutoff;
- `v2_acceptance_path=horse-racing/jrdb/forward-acceptance/YYYYMMDD.json`.

Leave the legacy `analysis_artifact_id`, `analysis_generation_id`, `course_fit_artifact_id`, `race_lap_artifact_id`, and `freshness_acceptance_json` **empty**. Any mixture is rejected.

In **legacy v1**, leave `v2_acceptance_path` empty and provide all five preexisting inputs as before.

After v2 validation, `v056_day/source_audit/forward_source_lock.json` pins selected source generations, hashes, cutoff and independent acceptance. `operation_handoff.json` includes `source_contract_version=v2`. All downstream v0.5.6 Prediction and Confidence Freeze logic stays unchanged.

## Fail-closed policy and limitations

- A successful Data Storage fallback run does not automatically authorize its output as the latest CURRENT. Its exact generation/transport digest and accepted receipt must be independently recorded and reviewed.
- If the data exists only as a transient Actions fallback artifact and has not been staged as an accepted SHA-pinned Drive ZIP, v2 cannot ingest it. This must be resolved by the dedicated producer operation, **not** by inventing an Artifact ID or allowing a free-form URL.
- T1 does not discover arbitrary Drive files, create or promote producer CURRENT, repair old source snapshots, ingest SED, or infer the latest completed race date.
- This PR does not ship an accepted 2026-11-21 source record; thus **live T1 cannot run via v2 until the real producer acceptance is prepared and verified.**
- Existing v1 replay contracts and all published freezes remain unchanged.

## Tests

New: `tests/test_racenote_forward_source_v2.py`; existing: `tests/test_racenote_a05_forward_freshness.py`. New PR CI `.github/workflows/racenote_forward_t1_v2_tests.yml` runs both and checks source compilation and YAML. A full forward end-to-end replay with real independently accepted data remains the final gate before production use.

# RaceNote Reader View real-data E2E — 2026-09-08

## Purpose

Verify the GPT-side Reader View design against a normal production `[RACENOTE_REQUEST]` artifact without changing the authoritative RaceNote v1.0 generation contract.

## Request

- GitHub Issue: `#467 [RACENOTE_REQUEST] reader-view-e2e-20260908-nakayama11`
- target: 2024-12-28 中山11R
- production workflow run: `34179828493`
- checked-out head: `68bcfb1209963f70afe8e3b94e825671d8377f85`
- task exit code: `0`
- collect exit code: `0`
- Archive resolution: `resolved`
- Archive tag: `jrdb-racenote-archive-202412-v1.0`
- used backend: `racenote_archive`

## External enrichment artifacts

Google Drive remained an external acquisition source resolved by GPT's Google Drive adapter. No Drive-specific bridge was added to RaceNote.

Verified inputs:

- Analysis Lite: `jrdb_analysis_rolling_v1_2_historyidx_20260907_094540.sqlite`
  - 60,569,456 bytes
- Stats Mart: `jrdb_stats_mart_2016_2025_v1_1_clean_20260901.sqlite`
  - 56,254,464 bytes

The production Issue received normal Drive URLs for these resolved artifacts, preserving the existing Request Router contract.

## Production artifact

GitHub Actions artifact:

- name: `racenote-reader-view-e2e-20260908-nakayama11-34179828493`
- artifact id: `10038501848`
- artifact archive digest: `sha256:b66b4a5f761a7b9f5653242100d0db56999ceb32aa6663c647e919f0c9581267`

Inner authoritative request ZIP:

- `RaceNote_20241228_中山_11R.zip`
- ZIP bytes: 25,571
- `request_manifest.json`: 2,324 bytes
- `race_bundle_20241228_中山11R.json`: 264,682 bytes
- runners: 18
- source schema: `1.0`
- authoritative bundle raw SHA-256: `b9e82e8db7d7b514dbf9bde962317d9d7487b93d192fba4dc2e23f645435e46f`

## GPT-side Reader View transformation

The retrieved authoritative ZIP was decorated after acquisition using the Reader View v0.1 contract.

Generated:

- `RaceNote_20241228_中山_11R_reader.zip`
- decorated ZIP bytes: 44,301
- `reader_view_20241228_中山11R.json`: 134,621 bytes
- Reader View count: 1
- hoisted shared contexts: `stats`, `historical_profile`

Reader View payload reduction relative to the pretty authoritative bundle:

- authoritative bundle: 264,682 bytes
- compact Reader View: 134,621 bytes
- reduction: **49.14%**

The decorated ZIP is larger than the source compressed ZIP because it intentionally retains the authoritative bundle and adds the derived Reader View. Reader View optimizes GPT reading, not ZIP storage size.

## Lossless validation

Semantic SHA-256:

- source: `614560e23f06e43a358af904c12bd4d9f9a0ffb5acdde1f7de9a537eac220115`
- expanded Reader View: `614560e23f06e43a358af904c12bd4d9f9a0ffb5acdde1f7de9a537eac220115`

Result: **PASS**

Additional checks:

- source `race_bundle_*.json` bytes preserved exactly in decorated ZIP: **PASS**
- Reader View expansion equals source semantic JSON: **PASS**
- `source_semantic_sha256` validation: **PASS**
- no field omission policy: retained
- no prediction/scoring logic: retained
- production Request Router output contract: unchanged

## CI evidence

Reader View / ZIP adapter regression workflow:

- workflow: `RaceNote Reader View tests`
- run: `34179585551`
- conclusion: `success`

This includes compile checks plus `test_racenote_reader_view` and `test_racenote_reader_zip` regressions.

## Decision

Reader View v0.1 is accepted as a GPT-side, reversible read-optimization layer.

Normal operation should be:

```text
user asks for one RaceNote race
  -> existing [RACENOTE_REQUEST]
  -> authoritative RaceNote v1.0 ZIP
  -> GPT retrieves artifact
  -> GPT-side Reader ZIP adapter
  -> GPT reads reader_view_*.json first
  -> race_bundle_*.json remains authoritative fallback/audit source
```

Do not move Reader View into the source-of-truth bundle schema and do not make the production Router depend on Reader View. Future lossy/salience-oriented views require a new explicitly versioned policy and separate evaluation.

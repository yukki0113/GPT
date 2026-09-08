# RaceNote Reader ZIP Adapter v0.1

## 1. Purpose

`src/racenote_reader_zip.py` is a GPT-side consumer adapter for normal RaceNote request artifacts.

The production Request Router continues to generate the authoritative RaceNote v1.0 ZIP without depending on Reader View. After GPT retrieves that ZIP from GitHub Actions, Google Drive, or another artifact channel, the adapter creates a new ZIP containing reversible `reader_view_*.json` files.

```text
[RACENOTE_REQUEST]
  -> authoritative RaceNote request ZIP
  -> GPT artifact retrieval
  -> racenote_reader_zip.py
  -> Reader View decorated ZIP
  -> GPT first-read / prediction work
```

This keeps acquisition/storage concerns separate from the RaceNote production generation contract.

## 2. Responsibility boundary

The ZIP adapter MUST NOT:

- change `race_bundle_*.json` bytes;
- remove authoritative bundles;
- change RaceNote schema v1.0;
- rank horses, score horses, or recommend bets;
- infer missing observations;
- modify historical `as_of_exclusive` semantics.

It only adds Reader View files and Reader View metadata to a copied request manifest.

## 3. Output contract

Input:

```text
RaceNote_YYYYMMDD_開催_NR.zip
├─ request_manifest.json
└─ race_bundle_*.json
```

Output:

```text
RaceNote_YYYYMMDD_開催_NR_reader.zip
├─ request_manifest.json
├─ race_bundle_*.json
└─ reader_view_*.json
```

The adapter refuses in-place overwrite; the authoritative source ZIP remains available as an unchanged fallback/audit artifact.

For every generated Reader View, the manifest records:

- `view_version`
- `source_bundle`
- `reader_view`
- `source_semantic_sha256`
- `roundtrip_validation = PASS`
- compact Reader View byte size

At ZIP level it also records `reader_view_version` and `reader_view_count`.

## 4. Reader View generation

The adapter delegates semantics to `src/racenote_reader_view.py`.

For each authoritative bundle:

1. decode the v1.0 JSON;
2. build Reader View v0.1;
3. expand it back to the authoritative semantic object;
4. require semantic SHA-256 validation PASS;
5. serialize the Reader View as compact UTF-8 JSON.

If any bundle fails this process, the adapter fails rather than publishing a partially unverifiable Reader View ZIP.

## 5. Idempotent regeneration

If an input ZIP already contains top-level `reader_view_*.json`, those derived files are replaced by newly generated Reader Views.

Authoritative bundles and unrelated members are preserved.

This allows GPT to re-run the adapter when Reader View implementation changes while keeping the source RaceNote bundle as the stable reference.

## 6. CLI

```bash
python src/racenote_reader_zip.py \
  RaceNote_20241228_中山_11R.zip
```

Default output:

```text
RaceNote_20241228_中山_11R_reader.zip
```

Explicit output:

```bash
python src/racenote_reader_zip.py \
  RaceNote_20241228_中山_11R.zip \
  --output ./reader/RaceNote_20241228_中山_11R_reader.zip
```

## 7. Standard GPT usage

For a normal one-race request, GPT should use this order:

```text
1. request/generate RaceNote by the existing production route
2. retrieve the resulting ZIP
3. run the Reader ZIP adapter
4. read reader_view_*.json first
5. retain race_bundle_*.json as authoritative fallback/audit source
```

Google Drive remains an external storage/acquisition channel handled by GPT's Drive adapter. RaceNote does not gain a new Drive-specific bridge or persistent Drive File ID dependency.

## 8. Validation

`tests/test_racenote_reader_zip.py` covers:

1. authoritative bundle bytes are preserved exactly;
2. generated Reader View expands to the source semantic bundle;
3. Reader View manifest metadata is emitted;
4. multiple race bundles are supported;
5. stale derived Reader Views are replaced;
6. missing request manifest is rejected;
7. in-place source ZIP overwrite is rejected.

Dedicated CI: `.github/workflows/racenote_reader_view_tests.yml`.

The core reversible transformation remains covered separately by `tests/test_racenote_reader_view.py`.

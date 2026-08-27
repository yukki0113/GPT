# RaceNote Archive Phase A/B validation - 2026-08-27

RaceNote Archive v0.1 designのstorage contractと実JRDB roundtripを検証した記録です。

## Scope

Phase A:

- base RaceNote v0.2 JSON -> monthly SQLite shard
- zlib compression
- exact / semantic SHA-256
- all / venue / race lookup
- exact-byte restore
- full-shard validation
- provenance validation

Phase B:

- real JRDB PACI -> base v0.2
- base v0.2 -> Archive
- Archive -> restored base v0.2
- restored base -> production RaceNote v1.0
- direct enrichmentとのsemantic equivalence

## Phase A synthetic regression

Issue:

`#136 [RACENOTE_ARCHIVE_TEST] phase-a-storage-regression-20260827`

Result:

- workflow run: `33059766066`
- test exit: `0`
- status: PASS
- head SHA: `286d246240162c56a6536130758edc4529bd9cd8`

Covered:

- `metadata.generated_at`だけ違うbundleはsemantic hash一致
- race内容を変更するとsemantic hash不一致
- target日当日の`recent_runs`をfuture leakageとして拒否
- target month外bundleの除外
- build -> SQLite -> readのexact-byte roundtrip
- date / venue / race lookup
- wrong-month shardのreader拒否
- SQLite integrity/full bundle scan

Provenance label制約追加後も再実行した。

Issue:

`#139 [RACENOTE_ARCHIVE_TEST] phase-a-provenance-regression-20260827`

Result:

- workflow run: `33060219671`
- test exit: `0`
- status: PASS
- head SHA: `590c172cc50fec877b25eec9503dc57d8829062f`

`source_ref`は短いlogical labelだけを許可し、URL/path/external service locationを保存しない。正確なsource provenanceは`source_input.filename + sha256 + source_period + role`で保持する。

## Phase B real JRDB roundtrip

Target:

- date: 2026-05-09
- venue: 京都
- race: 11R 京都新聞杯
- source: JRDB PACI

Issue:

`#140 [RACENOTE_ARCHIVE_POC] real-roundtrip-20260509-kyoto11`

Workflow run:

`33060368229`

Checked-out SHA:

`0b628eaddf9ba8aceee47ff38f429c62fa2b8a94`

Result:

```text
base exact-byte match       PASS
final v1 semantic match     PASS
archive schema              1.0
stored base schema          0.2
archive race_count          1
full-scan verified bundles  1
publishable                 true
provenance_status           complete
```

Hashes:

```text
base bundle SHA-256
303aee5a0671c87ddf9c510dc2e2b3048bca497c95e54a853634fc4c9378100c

base semantic SHA-256
976a464cb5cc13a20d9a7dac00e1e0a35603c834a13ef687f06689185f8e8bc9

final RaceNote v1 semantic SHA-256
aa0958c1d821748f76bfcb178ed4ff48a5202a819d65be95a6c84a5564d91fd1
```

The final v1 semantic hash is identical to the previously accepted production Kyoto Shimbun Hai regression baseline.

## Size observation

One real base bundle:

```text
base JSON bytes          229,500
zlib BLOB bytes           22,495
BLOB / JSON ratio          0.098
single-race SQLite bytes  61,440
```

The SQLite number contains fixed database/page overhead and is not a monthly-size estimate. The BLOB ratio is the useful initial signal for monthly-shard sizing. A full-month PoC is required before setting transport/performance thresholds.

## race key correction

Base RaceNote v0.2 intentionally does not expose the internal JRDB race key.

Archive lookup therefore uses:

```text
PRIMARY KEY (race_date, venue_code, race_no)
```

`source_race_key` is optional and must not be guessed from GPT-facing JSON. It may be stored only when an upstream PACI/Raw-aware builder supplies the authoritative key. Non-null `source_race_key` values are unique.

## Conclusion

Phase A/B validates the storage boundary:

```text
PACI / Raw
  -> base RaceNote v0.2
  -> monthly RaceNote Archive
  -> exact base restore
  -> current production enrichment
  -> final RaceNote v1.0
```

Archive storage does not alter RaceNote semantics. The next implementation step is request-router integration with Archive preferred for historical base retrieval and the existing PACI/annual-Raw paths retained as safe fallback.

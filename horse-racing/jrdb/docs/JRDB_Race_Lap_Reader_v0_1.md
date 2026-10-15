# JRDB Race Lap Parquet / Store / Reader v0.1

The common consumer entrypoint is `src/jrdb_race_lap_reader.py`.
RaceNote, RRDB and Research consumers can retrieve a stable JSON-compatible
object without knowing Parquet columns or DuckDB SQL.

```python
from pathlib import Path
from jrdb_race_lap_reader import RaceLapReader

reader = RaceLapReader.from_parquet(Path("/data/jrdb/race_lap.parquet"))
context = reader.get_race_context("05264501")
contexts = reader.get_race_contexts(["05264501", "01262501"])
```

Unknown keys return `None`; batch results include every normalized input key.
Keys use `str(value).strip()` and must have exactly eight characters. Each
nonempty batch executes one parameterized Parquet query, regardless of key count.

## Build from canonical SED

```bash
PYTHONPATH=tools/data-storage python -m data_storage check-deps
python horse-racing/jrdb/src/jrdb_race_lap_dataset.py \
  /data/SED260829.zip /data/SED260906.zip \
  --output /data/race_lap.parquet --audit /data/race_lap.audit.json
```

Use the dependencies pinned in `tools/data-storage/requirements.txt`
(DuckDB 1.1.3 qualified). Both output paths reject existing files by default;
`--replace` explicitly permits replacing an earlier build. Input paths cannot
be overwritten. Output is staged and validated before publication. Parquet and
audit are separate files; callers should accept a generation only after the
command succeeds and the audit SHA matches the Parquet.

Inputs are current canonical snapshots, never a merger of preliminary and
refreshed copies. Rebuild from canonical SED after a refresh. This builder does
not fetch JRDB Raw, publish Drive artifacts, or update any current pointer.

## Contracts and ownership

- Dataset: `JRDB-Race-Lap-Parquet-0.1`, one row per canonical `race_key`, DATE
  race date, native `INTEGER[]` distances and `DOUBLE[]` times, ZSTD compression.
- Evidence: `JRDB-Race-Lap-Evidence-0.1`, validated by
  `schema/race_lap_evidence_schema.json` (Draft 2020-12). The major objects are
  `race`, `coverage`, `laps`, `shape`, `srb_context`, `provenance`, and `policy`.
- Shape: `SRB-Neutral-RaceShape-v0.1`. `jrdb_race_lap_shape.py` owns the existing
  Phase 3B calculations. The legacy RaceNote evidence module imports it and
  retains its output contract. No metric formula is duplicated.
- `jrdb_raw.Parser.sed/srb` own byte interpretation;
  `jrdb_race_lap.normalize_race_laps` owns distance-aware normalization.
- `jrdb_race_lap_contract.py` owns internal columns and physical invariants;
  `jrdb_race_lap_store.py` owns read-only DuckDB access and decoding;
  the Reader owns evidence projection and cumulative segment reconstruction.

Store construction scans the snapshot to reject missing/wrong column types,
null/duplicate/noncanonical keys, empty datasets, mixed/unexpected versions,
invalid JSON, non-finite numbers, invalid segment layout/count/distance,
coverage/availability inconsistencies and missing provenance. Each lookup also
validates returned rows. Supply an immutable Parquet snapshot for the Store's
lifetime; construct a new Store after replacing a snapshot. Connections open
and close per call; no persistent DuckDB/SQLite database is created.

SRB absence is an acquisition/build error. An existing SRB record with all lap
slots blank retains its race row as `NO_LAPS`, with empty sequences and null
Reader shape metrics (including pace-up). Optional context and its availability
flag remain independently preserved. Physical pace-up is retained for audit.
Blank comments canonicalize to null. Track bias retains the official parser's
raw object, including blank/null values. Optional context is available when
pace-up, any nonblank bias value, or a nonblank comment exists.

The first 100m/150m partial segment is preserved in raw laps but excluded from
200m comparisons. Early 3F/delta are unavailable; late 3F needs three full
segments. No partial-time extrapolation is performed. Fastest segment numbering
uses the original sequence, including the partial first segment.

## Policy boundary

SRB is post-race, leader-based race evidence, not individual horse sectionals.
For a prediction on date D, only `source_race_date < D` is usable. The Reader
exposes `HISTORICAL_ONLY_AS_OF_EXCLUSIVE` and `NO_ADDITIVE_SCORE`; it receives no
target date and does not enforce a consumer's target-date selection. Consumers
must enforce the exclusive date boundary before prediction use.

No categorical thresholds, RaceNote marks/scoring, or RRDB signal semantics
are changed. Production consumer integration remains a separate task.

## Reproducibility

Rows sort by race date and key, independently of input archive order. No build
timestamp is embedded. The audit records coverage counts, date bounds, versions,
validation status, output size and SHA-256. Byte determinism is qualified within
the same writer/runtime version; it is not promised across DuckDB upgrades.

Verification and the two-day real-data smoke are recorded in
`JRDB_Race_Lap_Reader_Audit_20261015.md`.

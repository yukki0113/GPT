# BRDB research historical relations v0.4

`HistoricalRelationsReader` requires an explicit research generation path, ID and manifest SHA. It calls the v0.3 history Reader for the child's dated profile. For each requested date it constructs a `HorseMasterIndex` from annual selected snapshots available by that date plus daily profiles available by that date, and calls the existing `resolve_first_generation` guards. A date later than the last available daily observation is rejected. If any daily candidate has invalid or conflicting history, the entire date fails closed, since its unknown identity could make another candidate non-unique.

The alias ledger lacks independently established availability dates. v0.4 uses an empty alias index, permitting exact matches only; it does not infer a parent from a name alone. Parent resolution uses name, birth year and expected sex, candidate uniqueness, and the existing lineage and dam/BMS guards. The resolved parent's own as-of profile and source are returned with each relation. `parent_relation.parquet` is used only by the audit for a static comparison, never for resolution.

The graph traverses sire/dam edges, evaluating each node at the same `as_of`, to a maximum of five generations. The BMS relation is the dam's sire and corresponds to generation two. Cycles and unknown edges are explicit; partial coverage does not establish that an ancestor is absent. A single date's index and relations are cached and replaced on date change; returned relation objects are copied so clients cannot mutate the cache.

Dates are inclusive; actual publication time on race day and cancellation/start status are not known. Annual profiles are selected snapshots only. The fixed audit covers 2026-01-04 to 2026-10-25 and 10,680 horses / 39,543 KYI declarations. It is research-only and does not read or write CURRENT.

Inputs: #2223 approved ZIP SHA-256 `672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4`, #2230 approved ZIP SHA-256 `6eee5cc3ad8f6afe2b2ee4a2138a7efdfd7c61b244b5ed7a59668d73854dffdf`; generation manifest SHA-256 `7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c`; fixed cohort input SHA-256 `5bd031a957fc5a311068c00b7c313bca20ccccb272bce5962e7cc223935ebb39`. The cohort CSV is `verification/cohort_entries.csv` in the #2223 ZIP.

Reproduce from repository root with Python and DuckDB installed:

```sh
PYTHONPATH=horse-racing/brdb/src python -m unittest discover -s horse-racing/brdb/tests -p 'test_brdb_research_historical_relations_v04.py' -v
PYTHONPATH=horse-racing/brdb/src python -m unittest discover -s horse-racing/brdb/tests -p 'test_brdb_research_history_reader_v03.py' -v
PYTHONPATH=horse-racing/brdb/src python horse-racing/brdb/src/audit_brdb_historical_relations_v04.py --generation GENERATION_DIR --cohort COHORT_ENTRIES_CSV --output OUTPUT_DIR
```

The output includes every declaration with resolved IDs, guard results, temporal source provenance and ancestor paths; earliest-entry per horse; day and month aggregates. Detailed row outputs belong in the approved Drive artifact. `max_rss_kib` is environment dependent and is excluded from deterministic summary comparison.

# Research history Reader v0.3 — Issue #2230

`ResearchHistoryReader` requires an explicit generation ID and manifest SHA-256. It uses the v0.2 Reader's manifest, PASS, research-only, file-hash, cohort and selected-source checks, plus the pinned manifest hash and parent relation row count. No CURRENT or production system is used. The `as_of` argument is mandatory and must be a real `YYYYMMDD` date.

For daily additions the Reader validates and selects valid observations with profile date and archive date at or before `as_of`. Selection takes the maximum `(profile_data_date, archive_date, archive, member, line_number)` tuple, exactly as the builder does. A semantic conflict on any eligible profile date fails closed for that horse. Invalid JSON, field type, identity, date, semantic hash or source metadata yields `INVALID_SOURCE`; future observations do not participate. Annual horses retain the selected annual snapshot only, and return `UNSUPPORTED_ANNUAL_HISTORY` before its availability. This is not an annual history reconstruction.

All parent IDs are deliberately `UNKNOWN` in v0.3, including annual horses: the current relation table is never applied to a historical child. No ancestor paths are exposed, avoiding future identity leakage. Same-day UKC distribution time is unknown; date inclusion cannot establish information availability before a particular race time. Outside the input observation period, the Reader can only use the snapshots actually present. KYI represents declarations, not confirmed starters.

Pinned real inputs: Issue #2223 artifact SHA-256 `672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4`; generation manifest SHA-256 `7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c`; prior cohort CSV SHA-256 `5bd031a957fc5a311068c00b7c313bca20ccccb272bce5962e7cc223935ebb39`. The latter carries prior static/latest relation audit flags; the new audit verifies its SHA and actually calls the history Reader on every row.

For Python with DuckDB installed, from the repository root:

```sh
PYTHONPATH=horse-racing/brdb/src python -m unittest discover -s horse-racing/brdb/tests -p 'test_brdb_research_history_reader_v03.py' -v
PYTHONPATH=horse-racing/brdb/src python horse-racing/brdb/src/verify_brdb_research_history_v03.py --generation GENERATION_DIR
PYTHONPATH=horse-racing/brdb/src python horse-racing/brdb/src/audit_brdb_research_history_v03.py --generation GENERATION_DIR --cohort COHORT_ENTRIES_CSV --output OUTPUT_DIR
```

GENERATION_DIR and COHORT_ENTRIES_CSV are `generation/` and `verification/cohort_entries.csv` from the approved #2223 artifact. Audit reads all 39,543 history records and validates each valid record; the research Reader is called for all 39,543 KYI declarations. Output row-level CSV contains source provenance and should remain in the approved Drive folder.

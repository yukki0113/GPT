# P0.1 correction record — 2026-11-24

Scope: P0-01, P0-02, P0-04 only. No prediction implementation, Canonical regeneration, feature promotion, or 2026 data ingestion.

- P0-01: Original ledger SHA and publication audit match the P0 evidence. The ledger entry for ACCEPTED.json differs from the actual accepted bytes; the latter match the original publication audit. The cause is not proven. Register the exact correction in `../config/canonical_integrity_corrections.json`; preserve the original Drive bytes, including CHECKSUMS.sha256, and apply only under the specified fail-closed conditions.
- P0-02: Define historical-result derived feature contract in CANONICAL_DATA_SPEC.md. Initial cutoff is prior calendar days in JST, no same-day results. Keep POST_ONLY direct block and all PENDING snapshot restrictions. Future research must implement and test the contract before adoption.
- P0-04: Correct the 2026-09-18 handoff description: weather and track condition are pre/race, PRE_SAFE / RACE_DAY / ALLOW, not post. Historical observation timestamps are not recorded. Existing field catalog and schema need no changes.
- Deferred: P0-03 entity resolution (P2/P3); P0-05 2026 coverage extension (separate data work).

P1 descriptive research may proceed after the specification and correction record are reflected. This is not a new full-generation physical audit or a claim of implemented prediction guards.

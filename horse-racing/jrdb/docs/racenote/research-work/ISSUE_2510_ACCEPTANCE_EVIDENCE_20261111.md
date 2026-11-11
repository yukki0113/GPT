# Issue #2510 acceptance evidence inventory (2026-11-11 JST)

Production mixed-source gate: DISABLED. No new T1 or Freeze is accepted by this record.

## CI triage

- Commit 096fdf2: v0.5.6 contract, A05 freshness, Warehouse compatibility, v0.5.4 guard and EdgeDB audit pass.
- Historical v0.5.2 golden run 42928741953 fails at frozen BTDAY-0059/20260510: stored forecast_prep handoff has `rrdb-recommendation-signals-v0.3`; current `racenote_save_venue_batch_v046.py` expects v0.4. This is an old frozen handoff versus current validator contract; source routing is not in the failing path. Do not rewrite the frozen input or relax the contract. A versioned replay path or a separate current-contract fixture is needed.
- A03 run 42928741950 and A04 run 42928742258 pass offline regressions, then fail when `gdown` cannot retrieve approved public Drive file IDs `1ljLg_jxVdZtpJ_Aqku0L93y8nwnfXUTQ` and `1q7pmoTRsg27d--xi5HhtTaJXAI_TdzUi`. No source/contract changes made.

## Reusable evidence, not new-route acceptance

- Historical BTDAY-0181/2025-05-25 on main has an accepted Warehouse generation `jrdb_normalized_warehouse_v1_2010_2025_g20260921`, 36 Reader races, and blind flags true/false/false. This proves the existing path readback, not the new v2 reservation/T1. The full accepted Warehouse object set, target-year BAC/KYI archives, and accepted source receipt must be staged with SHA verification for a new historical T1.
- PACI261107.zip available locally: SHA-256 `61ffacbb935ee5064ba84080e7c6921c080879b43b9bed9153d6cc27a4d81057`, ZIP CRC PASS, BAC 36, KYI 501. Existing FORWARD Analysis artifact 13121913163 covers through 2026-11-01. These checks do not establish a BTDAY T1. A canonical PACI receipt, accepted date-specific RRDB snapshot and receipt, Course Fit and RaceLap materializations, and SHA-pinned staged artifact are still required.

## New-route acceptance pending

Neither source has a new-route T1, Reader artifact, SHA-bound main readback, or two-phase Freeze proof. No `PASS` gate proof is recorded. The v2 inventory remains PENDING, so NEXT cannot reserve these dates. Once the listed accepted inputs are staged, run source-specific preflight and the shared T1 workflow, then save artifact ID/SHA, Reader counts and hashes, main readback and blind/freeze verification as separate per-source evidence.

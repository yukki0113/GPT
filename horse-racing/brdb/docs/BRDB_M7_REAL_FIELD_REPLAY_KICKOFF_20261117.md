# BRDB M7 real-field integrated research replay — kickoff audit (2026-11-17 JST)

Status: **IMPLEMENTATION GATE OPEN / REAL INTEGRATED E2E NOT YET EXECUTED**. Tracker: [#2628](https://github.com/yukki0113/GPT/issues/2628).

## Basis checked on main
- `docs/BRDB_MILESTONE_RECONCILIATION_20261116.md`: M7 v0.3 research candidate accepted; real integrated-field replay, qualified interpretation, consumer regression, and explicit graduation remain pending. M6 #2395 BLOCKED.
- `docs/BRDB_INTEGRATED_BLOOD_REVIEW_CONTRACT_v0_2_CANDIDATE.md`: output contract, not a completed real-field producer. All horses must be represented; four evidence components are required, and no missing component can be invented.
- `docs/BRDB_INTEGRATED_BLOOD_REVIEW_CONTRACT_v0_3_CANDIDATE.md` and `src/brdb_integrated_review_v03_candidate.py`: research-only merger accepts a *pre-existing* v0.2 field and D4 sidecar, guards race identity and every horse ID/number, preserves base semantics.
- `src/run_brdb_d4_paci_e2e_acceptance.py` and PR #2603: accepted full-field PACI source `PACI261115.zip` (`05265412`, 18 horses), D3 fixed inputs, D4 sidecar twice, 66 research-only observations (including four zero-evidence horses).
- PR #2619: exact PACI user-side Drive bytes were observed before the scheduled off; provider release timestamp not independently attested.
- PR #2620: v0.3 candidate 12 schema/adapter tests PASS, but not proof of a real v0.2+v0.3 integration.
- `src/brdb_blood_review.py`: frozen v0.1 is a separate non-scoring contract and cannot be silently substituted for the v0.2 race-level contract.

## Gap and engineering decision
An accepted **real PACI full-field v0.2 producer** was not established by the documents and code inspected for this audit. Before invoking `merge(base_v02, d4_sidecar)`, confirm an existing producer and its real-input provenance; if absent, build a separate research-only v0.2 field adapter using source-qualified ①–④ outputs and approved JRDB parser/Reader. Do not claim missing producer absence from search misses alone.

This gate must be executed with the **same exact field** at both sides of the v0.3 merge; a synthetic v0.2 fixture merged with real D4 does not qualify.

## Next implementation acceptance sequence
1. Confirm the upstream real-field ①/②, ③, ④ candidate outputs and source date/identity requirements for `05265412`; enumerate missing canonical assets.
2. Produce a v0.2 candidate payload for exactly 18 horses with complete horse-id and horse-number map; no name-based identity fallback; guard as-of-exclusive and independent component statuses.
3. Validate the existing v0.2 JSON Schema with jsonschema (no skipped validation).
4. Use the unmodified `brdb_integrated_review_v03_candidate.merge` and existing v0.3 schema to merge exact D4 18-horse sidecar.
5. Run twice with identical pinned inputs, compare byte SHA, verify every horse and zero-evidence cases; test mismatch rejection, later data leakage, factor/score injection and safety-state promotion.
6. Save fixed inputs/outputs or only provenance receipts in their authorized locations; keep individual historical/horse records out of public Git; commit test source and audit summary.
7. Mark the gate PASS only after execution and artifact readback, not upon fixture-only tests. Move to interpretation policy/consumer regression only after separately accepting this research gate.

## M6 parallel lane
Issue #2395 stays OPEN/BLOCKED. Conditional 2016–2025 retrospective evidence does not satisfy independently attested historical as-of or pre-off frozen paired predictions. Do not reclassify M6 based on M7 engineering work.

## Absolute non-goals
No CURRENT pointer change; no RaceNote/PWA/Newspaper deployment; no change to frozen `brdb-review-v0.1` or v0.2 candidate contract; no scoring/positive-negative factor generation; no unreviewed lineage crosswalk; `prediction_safe=false` and `AS_OF_UNVERIFIED` retained where applicable.

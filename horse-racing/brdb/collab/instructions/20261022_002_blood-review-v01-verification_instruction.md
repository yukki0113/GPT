# BRDB Blood Review v0.1 — verification and freeze task

Status: READY FOR CODEX VALIDATION (do not report DONE until evidence exists)
Date: 2026-10-22
Target: yukki0113/GPT main at latest HEAD
Scope: horse-racing/brdb/ only, except read-only inspection of RaceNote P2 code/data.

## Goal

Complete phase ② Blood Review v0.1 with executable test evidence and an actual representative-race field dry-run. The implementation baseline is already committed to main. Do not rebuild 16-year UKC, do not modify the immutable generation, do not change RRDB/RaceNote/PWA production.

## Sources

- horse-racing/brdb/src/brdb_blood_review.py
- horse-racing/brdb/src/brdb_racenote_p2_adapter.py
- horse-racing/brdb/tests/test_brdb_blood_review.py
- horse-racing/brdb/tests/test_brdb_racenote_p2_adapter.py
- horse-racing/brdb/src/brdb_current.py
- horse-racing/brdb/docs/BRDB_BLOOD_REVIEW_IMPLEMENTATION_v0_1.md
- horse-racing/jrdb/src/racenote_history_engine.py
- horse-racing/jrdb/docs/racenote/RACENOTE_PEDIGREE_ENRICHMENT_DESIGN_v0_1.md

Canonical CURRENT artifact transport:
- BRDB config/public_drive/brdb_current_v0_1.json (pin SHA, no ad hoc download)
- Data storage common tools for DuckDB, do not replace with another engine.

## Required implementation review

1. Run all BRDB tests; fix failures and add regression coverage for fixes.
2. Verify adapter real P2 producer fields, especially provenance, as_of, venue/surface/distance, and canonical horse_id. Reject stale, inconsistent, or missing P2. Preserve 0 starts as factual evidence.
3. Review security: never accept P2 by matching date only. Reject wrong cohort/horse identity, duplicate horse_ids, contradictory pedigree names. Ensure no input exposes post-target race results through review output.
4. Maintain phase boundary: review v0.1 is descriptive, scores/classification regional_type remain null.
5. Be cautious: UKC full snapshot 2010–2025 does not guarantee as-of identity for historical races. For dry-run, flag any profile_data_date > target_date as AS_OF_UNVERIFIED or restrict to date-safe current records. Do not silently use future-born/newly observed horses for a historical review.
6. Verify batch/single semantic equivalence for all target IDs, not only hand-picked horses.
7. Add a CLI runner under BRDB for fixed-input field replay if required; produce an aggregate-only report with target date/venue/race, counts by status, 0/partial/full P2 coverage, identities missing and reasons, fail-closed count, source commit, input references, tests, and no per-horse personally sensitive output.
8. Use a real RaceNote enriched authoritative race bundle, not invented fixture, for at least one full-field run. If current data not accessible, report this explicitly as BLOCKED and do not call Phase ② DONE.
9. Update BRDB REVIEW_CONTRACT, implementation doc, README and CONTEXT only if validated. Freeze `brdb-review-v0.1` fields and status semantics without breaking PWA.
10. Commit changes via PR, result report in horse-racing/brdb/collab/results/20261022_002_blood-review-v01_verification_result.md, including exact test command and PASS/FAIL counts. Do not merge automatically.

## Acceptance gates

- Existing and new focused tests pass in real Python environment, with version details.
- Real RaceNote P2 adapter accepts correct cohort and fails closed on wrong as-of/horse/venue/distance.
- Full-field batch run produces one record for every requested horse, missing included as statuses.
- No results leakage, no invented score, no name fallback.
- All unresolved gates explicitly BLOCKED, not ambiguously DONE.

# BRDB context

Status: Blood Review v0.1 validated and contract frozen on 2026-10-22.

Canonical pedigree storage is the immutable generation `eeca93556584a5b8`, read through `BloodReviewReader` and the SHA-pinned `brdb_current.py` resolver. Its transport manifest is `config/public_drive/brdb_current_v0_1.json`.

`brdb_blood_review.py` provides non-scoring single and field batch reviews. `brdb_racenote_p2_adapter.py` accepts only exact-cohort, exact-race, as-of-exclusive RaceNote P2 descriptive evidence. Profiles with `profile_data_date > target_date`, or missing profile date, return `AS_OF_UNVERIFIED` with facts withheld.

The review field and status freeze is `docs/BRDB_REVIEW_CONTRACT_v0_1.md`. Verification evidence and the real authoritative 9-horse field replay are in `collab/results/20261022_002_blood-review-v01_verification_result.md`. No PWA serving, score, regional taxonomy or CURRENT mutation is part of this phase.

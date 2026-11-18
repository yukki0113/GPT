# BRDB M6 — historical JRDB pedigree equivalence acceptance and scope reset (2026-11-18)

**Decision owner:** project user. **Decision:** accept the existing JRDB 2016–2025 annual files and their date-scoped KYI/UKC extraction as valid historical pedigree facts for BRDB analytical research. Treat the reported provider equivalence answer as a project-accepted operational premise, **not** an outstanding prerequisite requiring historical original-package byte equality or release-time signed evidence.

## What is accepted now

1. The pedigree attributes (canonical horse identity, sire, dam, broodmare sire, lineage identifiers when source-qualified) are effectively immutable facts of the horse. Corrected entry/alias/canonical ID matching is possible and must be guarded, but historic day-of-distribution bitwise equality is **not** a useful mandatory gate for pedigree-based research.
2. Use the existing 2016–2025 annual ZIP and reconstructed date-partitioned UKC/KYI as the accepted research input, with `source_equivalence_policy=USER_ACCEPTED_PROVIDER_EQUIVALENCE`. This is an **approved research policy**, not a forged `provider_timestamp_verified` assertion.
3. The existing 481,503/481,627 joinable declaration rows are sufficient for fixed-cohort retrospective study; the remaining 124 missing rows (2025-12-13/14) are a documented nonblocking exclusion. Record denominator/coverage and sensitivity. Never invent their pedigree or a canonical identity.
4. **Accepted M6 research findings already executed on main:** [conditional retrospective study](BRDB_M6_CONDITIONAL_RETROSPECTIVE_20261104.md), [PR #2408](https://github.com/yukki0113/GPT/pull/2408): five 2021–2025 chronological held-out folds, 235,700 entries / 17,239 races; source-exact baseline log loss `0.26121709072530674`, blood-added `0.2608869015289739`, Δ `-0.0003301891963328283`; modest reduction, not evidence of ROI or improvement over actual RaceNote.
5. As a result, **remove "independent historical per-file publication-time/byte-matching proof" as a M6 research blocker**. Existing archival observations (timestamps not authenticated) can remain in the audit log as facts but must not be repeatedly demanded as a blocking task. No repeated provider outreach for old delivery SHA is required.

## What remains a distinct empirical question

- A 2021–2025 chronological reconstructed historical hold-out is **valid retrospective predictive evaluation under this accepted input policy**; it is **not** a comparison against the actual RaceNote prediction pipeline.
- The baseline used in the completed study is a newly implemented non-pedigree logistic-regression baseline, *not* original RaceNote; the latter outputs marks/confidence and does not have historic horse-level probability pairs. Do not retrospectively transform historical marks into calibrated probabilities and claim a verified RaceNote lift.
- Two useful targets must not be conflated:
  - **M6-R:** research-only historical predictive incremental value of pedigree over the explicitly specified non-blood logistic baseline. **ACCEPTED WITH LIMITATIONS** by this policy decision, no pending provider byte/equivalence blocker.
  - **M6-P / RaceNote incremental value:** performance change when adding BRDB to the *actual* RaceNote forecasting workflow. **NOT YET MEASURED**; set up prospective paired evaluations if seeking a real RaceNote performance or scoring claim. Track this separately from the accepted historical M6-R. No premature `prediction_safe=true`, `AVAILABLE` as fitness verdict, or production approval.
- Existing P1-5 one-way cluster/annual diagnostics, correlation and multiple-testing limits remain properly reported as interpretation limitations, not reasons to retroactively invalidate the completed numerical result.
- Parent/horse ID alias mismatches, future-leakage during model fitting, lineage-code revisions, and result leakage still require normal quality gates; these are *different risks from pedigree-fact distribution timestamps*.

## Practical implementation order

1. Preserve all immutable prior logs/results/SHAs; record this policy choice as an explicit **new acceptance addendum**, not a rewrite of historical provenance.
2. Reclassify [#2395](https://github.com/yukki0113/GPT/issues/2395) from "blocked by historic blood-file provenance" to "historical comparative research accepted, actual RaceNote effect distinct/open"; mark already-executed P1-5/P1-6/study P1-7 appropriately. Do not leave a provider-original-byte check as a completion task.
3. Advance M7 research data/consumer reference display using accepted pedigree facts, provided the existing explicit research-only forecasts boundary is maintained.
4. Plan actual RaceNote optional uplift measurement as an engineering experiment with horse ID/race ID joined paired outputs; if producing new baseline/challenger probabilities, freeze both **before** results. That is an honest *new* evaluation gate, not a retroactive reason to stall completed pedigree history research.

**Production boundary:** this is an acceptance/policy change only; BRDB CURRENT, RaceNote ranking/marks/confidence, PWA and Newspaper production data or code remain unchanged. Historical UKC as-of timestamps are not cryptographically verified, and no statement falsely asserts they are. We simply no longer require that independent attestation to accept pedigree research.

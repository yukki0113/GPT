# BRDB B6 — JPDB debut evidence reference bridge v0.1 candidate (2026-11-24 JST)

Status: **PASS_RESEARCH_ONLY** for the design and fixed 4-race/42-declaration technical dual-source debut-specific link. No predicted outcome, no R4 authorization, no production, no change to the existing R3 contract, JPDB, RaceNote confidence Z, Freeze, CURRENT, Newspaper or PWA. B7 is next.

## Authority and scope

Main observed 569947dac871bce89f5762818b7151350f394000; B5 development branch parent 5362aa05a7102de3579b43000e6646ff1efb27a3. Handoff B6 requires actual JPDB contract verification, independent lanes, same race/horse identity, missingness and dependence checks, no modification of JPDB. JPDB R1 and R2 fixed-source research accepted; R2 SUGGESTIVE not certified. R3 common evidence technical acceptance and [newcomer acceptance](../../jrdb/docs/RACENOTE_R3_NEWCOMER_ACCEPTANCE_20261124.md) now cover 4R/42 declarations, with 630 general-start BRDB observations and 2142 JPDB evidence. Those blood observations are GENERAL_STARTS_NOT_DEBUT_SPECIFIC. June base-only and November M7 v0.3 contracts differ and must not be relabeled. The B6 bridge is a separate reference contract for B5 debut-specific evidence, not an R3 mutation or claim of R4 approval.

Reused accepted private R1, R2 and R3 newcomer archives from Library /JPDB/R1, /JPDB/R2, /JPDB/R3. R3 newcomer archive SHA256 21630ec1a6b4e51a837f2278a8d2a66853d7717b9edf222ec70df91294bba9a7 exactly matches current Git acceptance. Profile/receipt and per-race R3 detail pins independently obtained from current Git R1/R2/R3 acceptance documents/evidence JSON. Every selected original file SHA verified. Actual JPDB R1/R2 contracts and R3 source inspected; no JPDB computation reimplemented or rerun, only fixed-output binding checks and projection references. B5 exact runner (SHA 731ac75c2dca9f2664b305aed895f1055e9af95017136c9edcb786634d1d3041) reused with its unchanged B1–B4 dependencies and verified immutable inputs. Existing canonical PACI parser subset as B5; not full jrdb_raw.py byte certification. Canonical Drive PACI direct folder lookup; source bytes match JPDB pinned PACI SHAs. Existing Python 3.13.5 / DuckDB 2.0.1 / PyArrow 25.0.1 dependency_report success; local C execution, no Actions. B5 twice replayed on each target date; exact output and receipt bytes agree. Original 11/01 B5 55-horse acceptance preserved.

| Date | Race key | Declarations | R3 version | B5 replay |
|---|---|---:|---|---|
| 2026-06-13 | 05263305 | 7 | base-only v0.1 | 7/7 |
| 2026-06-13 | 09263306 | 13 | base-only v0.1 | 13/13 |
| 2026-11-15 | 05265404 | 12 | v0.1 | 12/12 |
| 2026-11-15 | 05265405 | 10 | v0.1 | 10/10 |

## Contract

New schema brdb-jpdb-debut-evidence-link-v0.1-candidate. Independent manifest SHA pin required; strict JSON duplicate-key rejection and source-byte SHA checks; R1/R2 acceptance proof hashes and R3 source assets bound to the same PACI. No incomplete field, duplicate/extra/mismatched target or alternate name match. Exact date, race_key_raw/horse_no/horse_id, planned PACI KYI jockey_code (not reference jockey or SED actual), cancellation flag, BAC A1 class, surface, distance and field size. Retain every declared runner, including missing evidence. RaceNote R3 detail version and per-race SHA retained. R1/R2/R3 observation identifiers, 17 axes × 3 windows, condition and periods, count reconciliation and native redundancy groups validated. All 2142 accepted JPDB references unchanged; refer back to full source R1/R2/R3 numbers/uncertainty without recomputing interpretation. B5 validator reused, references all 40 population cells and every relative cell for each horse. B5 temporal/status distinctions and individual history status retained. No general-start substitution, no numerical promotion of restricted pairing/relative evidence, no overwriting R3. All BRDB B5 cells are research references, not adopted scoring features. Full private source values remain at pinned assets; bridge is intentionally reference-only and is not itself a numeric feature matrix.

JPDB cutoff is strictly target date exclusive, 3Y/365D/90D with actual SED rider; B5 outcomes fixed <2026-01-01, 2017–2025 population and 2016 history, 2026 history gap true. JPDB prior-day availability assumed, stored PACI timing not attested, B5 historical relation as-of unverified. R1 candidate-start and R2 resolved-start denominators distinct from B5 actual starts. A1 race class versus first-observed candidate separate; no lifetime first certification. Same horse/race, same scheduled rider is a binding, not a causal link. SHARED_JRDB_HISTORY_NOT_INDEPENDENT across lanes; no additive votes, score, probabilities, outcome, market or marks. Low N and unavailable are not negative aptitude. All research flags false for prediction/production/R4.

## Real-data results

42/42 exact field identity and scheduled jockey/cancel matches; 42/42 dated blood profile. 2142 JPDB refs (1299 DESCRIPTIVE_ONLY, 518 INSUFFICIENT, 73 NO_HISTORY, 252 TARGET_CONDITION_UNAVAILABLE). 1680 B5 population refs (655 DESCRIPTIVE, 299 LOW_SAMPLE, 126 NO_SAMPLE, 600 SOURCE_UNAVAILABLE). 1230 relative refs (408 LOW_SAMPLE, 357 NO_SAMPLE, 170 FIRST_START_UNRESOLVED, 295 NO_PRIOR_OBSERVED_START). 246 target-relative pairs; 32/42 targets with at least one eligible relative first history. 5052 references total; not independent samples.

Fixed joint coverage: B5 A1 cohort vs JPDB ROLLING_3Y newcomer matching axes; blood positive N and rider positive N with unresolved_count=0; both N>=30 is a descriptive sample band, not significance, effect direction or production availability. All 42 retained in denominator. No pooled comparison of rates across domains.

| Blood lane | ALL both positive N | ALL both N>=30 | SURFACE both N>=30 | SURFACE_DISTANCE both positive N | SURFACE_DISTANCE both N>=30 |
|---|---:|---:|---:|---:|---:|
| SIRE_ID | 21 | 19 | 16 | 21 | 5 |
| BMS_ID | 28 | 22 | 18 | 25 | 5 |
| PARENT_ID_PAIR | 10 | 1 | 1 | 2 | 0 |
| LINEAGE_CODE_PAIR | 41 | 38 | 33 | 39 | 10 |

For ALL lineage pair, 41 both observed, 1 blood only, 0 jockey only, 0 neither; for ALL sire, 21 both, 1 blood only, 20 jockey only, 0 neither; BMS 28 both, 0 blood only, 13 jockey only, 1 neither; parent pair 10 both, 0 blood only, 31 jockey only, 1 neither. Two date receipts retain complete scope cross-tabs. Across dates, 35 distinct scheduled riders, 6 reused; 78 distinct resolved broad blood keys within lane, 18 reused; 246 unique relative IDs, no repeated IDs in these particular targets. Nested scopes, cohorts, rider windows, overlapping historical rows and selection/mount opportunity effects are not independent. Exact historical row intersection not measured from aggregate profiles; no claim of statistical independence or redundancy coefficient. Fixed 4R coverage is not population-wide or predictive validation.

## Quality and artifacts

15/15 B6 tests per date (3 common synthetic/hash/duplicate tests + 12 real-fixture checks), 30 executed checks across two runs; 27/27 B1–B5 regression with original 11/01 fixture. Original B5 regression on 11/15 initially failed its hard-coded future date 11/02, which is actually earlier than 11/15; no B5 source change. Re-run original fixture PASS; B6 new target-relative future-profile check PASS on both dates. New Draft202012 schema 2/2 with FormatChecker and score/production injection rejected. Both B5 replays and B6 links/receipts regenerated independently and byte equal; Library archive raw readback byte equal. No GitHub Actions/CI run claim.

Source SHA256:
- research/run_brdb_b6_local.py 0863355adfbedc0784ddf438c294e667848d246704fb47e76d7324488f372b51
- research/test_brdb_b6_research.py 95f5d0e2d749b8cbcc3a03af114272ec67d85305c037bd2594580ea2c7bdc4b1
- schema/brdb_jpdb_debut_evidence_link_v0_1_candidate.schema.json 32474e85b57afd2d7e6aaa7a0e712dc5e9dce21466bf34c62a7e71a63f0e89a4

Private Library /BRDB/Development_B6_20261124/PRIVATE_BRDB_B6_20261124.zip SHA256 80a2e55375104f0aaa6931f12d09dcffa3dbb990d5883d881735b534d3006831. Contains replay B5 outputs, manifests, B6 links and receipts, test logs. Original JPDB source archives and PACI stay separate. Restore archive layout and original private inputs (manifest path relative to its location; verify independently pinned source SHAs on relocation).

| Asset | 2026-06-13 SHA256 | 2026-11-15 SHA256 |
|---|---|---|
| PACI | 439c6622b5c32f44ff3e63b9aee404a8ec3f153bb246ab87d64c94965cebe8db | 3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050 |
| B5 review | f567373f006e1808e1b4c2d00e7018f6306614151b1732cd9fea271dcb76f59e | d75b0974a98d94ffb8d14aa17a90644386341f30843b710a2ffa2a0a026a08de |
| B5 receipt | ed444c257b799f6eec89d555b56f96853c0b5c1fc5d36f62b634ef61295920a9 | 23702f32bb20062474e4ddc057f8116bcf47d2bee687fdcc14c778998ffb0e96 |
| B6 input manifest | 4f87995dba3f8c0db11e7045af378faa0488cb9fd77513c6787065f43b02d317 | c7170de9a30e5859987d01de5575b3d9e6b93f87ce7eaa42498b1fbf47e2d0a0 |
| B6 link | 036b368f6d32a66b9a1f9710bc9bd7a113ed5365f34945edb33e39cb935a3e19 | 3a3dd1731af0f64bd37147596e4732a797ad1fbbffab47a2de5ce624eb9355b3 |
| B6 receipt | 71decd92bce2e8e889e96fe8821bbc910c2623c7d6c3bc1569c8b5fffea0e8e1 | 8d3893cf2924c17737d2313afcae1ecaaf0fcff7ff3f7328e716850b4a43e769 |

Replay with B5 dependencies and independently pinned manifest:
    PYTHONPATH=tools/data-storage python horse-racing/brdb/research/run_brdb_b6_local.py --manifest /private/manifest_20260613.json --manifest-sha256 4f87995dba3f8c0db11e7045af378faa0488cb9fd77513c6787065f43b02d317 --output-dir /private/new-output
    BRDB_B6_MANIFEST=/private/manifest_20260613.json BRDB_B6_MANIFEST_SHA=4f87995dba3f8c0db11e7045af378faa0488cb9fd77513c6787065f43b02d317 PYTHONPATH=tools/data-storage:horse-racing/brdb/research python -m unittest test_brdb_b6_research -v

## B7 handoff

Use this reference-only linkage design to construct a separate research feature extraction contract. B7 must freeze cohort and date/field splits, outcomes and fixed baseline before accessing holdout results. Keep A1 declarations separate from observed lifetime-first candidate; compare non-blood/non-jockey baseline, blood-only addition, jockey-only addition and both on exactly the same fields/time splits, retaining missingness. Align cutoff/history coverage intentionally (B5 2026 gap, JPDB 2023+), not silently substitute 2025 full-year aggregates into earlier historical targets; use strictly prior outcome windows with shared date cutoff and accepted research temporal limitations. Record sample/coverage differences, paired predictive metrics/calibration and dependency/selection confounding; no hard-coded additive votes, no R4/production or change to Z. This B6 does not execute B7 or certify the 11/01 55-runner cohort's JPDB coverage. No raw or horse-level data committed.

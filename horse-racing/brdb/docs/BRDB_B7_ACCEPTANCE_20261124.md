# BRDB B7 — fixed retrospective newcomer predictive comparison (2026-11-24 JST)

**PASS_RESEARCH_ONLY — experiment completed; incremental blood benefit NOT demonstrated by this fixed model.** No production authorization, no prediction-safe certification, no RaceNote Confidence Z/Freeze/CURRENT/PWA change. Do not infer blood uselessness, causal rider skill or actual RaceNote uplift. This is a conditional retrospective research comparison, not R4/R5 approval, market/ROI or true-forward evaluation.

## Protocol and provenance

[Pre-result frozen protocol](BRDB_B7_RESEARCH_PROTOCOL_20261124.md) committed at ed99e21f2ab395ac20c08070279258425cf1a91d (blob 726934f72589237fe11929ca3145c9d1ad920cd7) before numeric feature/model/holdout execution. Existing data years have been inspected in other research; this is not external preregistration or a previously unseen true-forward interval. Initial main 9968b6723facbb790212e0b7f555493afd1b7218; final main 5859bcd2659b3aa31ef1a92f44e118d8229fd1a7 (only JRDB R5-related files changed). B6 accepted at 3127db4ff6610a19a59d3581b6b484d6302cbb8e. No other project sources changed.

Reuse B3 setup/B1 verified Analysis 481627 rows 2016–2025, ten historical UKC partitions, immutable canonical pedigree/parent/lineage masters and B2 two cohorts, B4 guarded exact maternal paths and first three starts SQL. B1–B4 historical source provenance as accepted; 2017–2025 blood population, 2016 history to establish left edge. Nine accepted JPDB BAC/KYI/SED Parquet assets for 2023–25 exact SHA256/size pins in main `horse-racing/jrdb/config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json` blob e1657af2aa3066d19c52043d6f98136bbb9866d5, downloaded via native Drive, verified by runner. Canonical JRDB Reader/normalized assets, no new raw parser. JPDB history population and condition semantics verified against v1.1 / R1 code blobs 4b095d26a1f9083105d0958c4a1f5d5cb627a6c3 and 468557648bcddbdbde12775b731c3b488950397f. New B7 batched cumulative-date research query cross-checked against independent direct source counts; not invocation of the 2026-only R1 target builder. Python3.13.5, DuckDB2.0.1, PyArrow25.0.1, NumPy2.2.4 pinned shared offline runtime; dependency_report success. C execution, no new Actions or CI claim.

Historical target jockey = FINAL_KYI_PROXY; history = SED actual rider under JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1. The exact target release, later revisions, parent graph availability and contemporaneous historical UKC/KYI delivery are not strictly attested. 11/18 provider-equivalence research acceptance respected. No actual target SED rider used in features. No target result, odds, popularity, marks or KYI indices in features. JPDB 3Y clip from 2023-01-01; prior-date result cutoff strict for both lanes. Earlier holdout-year days update descriptive history online, not fitted coefficients. Separate output references do not imply statistical independence.

## Cohort and exclusions

A1 BAC flat race declarations; full KYI/SED/Analysis race/horse/date/class/surface/distance identity and one winner checked. A1 race class not lifetime-first status. No horse-level drop due to evidence missingness. Evaluation probabilities sum 1 over all declared runners, including nonstarters. Outcome-based completeness/unique-winner restriction is an evaluation boundary, not feature selection.

| Year | Purpose | BAC A1 races / declarations | Accepted races / declarations |
|---|---|---|---|
| 2023 | rider history warm-up | 302 / 3931 | 302 / 3931 |
| 2024 | train | 302 / 3982 | 302 / 3982 |
| 2025 | holdout | 304 / 4032 | 294 / 3910 |

2025-12-13 5R/60 and 2025-12-14 5R/62 (10R/122) excluded whole-field as Analysis class mismatch to A1; identity and outcome mismatch 0. Do not silently fix or impute these records. Historical result/UKC gaps on these dates remain source debt, not a missingness-based deletion. 2024/25 planned-vs-actual rider code differs 26/27 declarations respectively; 22/17 nonstarters retained. Individual prior history audit: no earlier observed JRA actual start in eligible train/holdout targets; KYI prior result reference present in 14/16 respectively, unresolved as lifetime-first certification. First-start status is not a feature or target selection filter.

## Features and models

24 population cells (B2 A1/first-observed cohorts × 4 B3 lanes × 3 fixed conditions ALL/SURFACE/SURFACE_DISTANCE), four B4 relative cells (same dam and maternal aunt/uncle, first and first-three), four JPDB A1 3Y cells (all flat, surface, venue/surface, exact surface/distance). B4 target graph constructed for all eligible declarations, not selected by realized start status. 32 cells per target, 252544 cells; log1p(n), shrinkage win/top3 rates, unavailable/no-sample/unresolved flags; fixed priors and smoothing per protocol. No raw ID as feature, no imputation of unknown identities. 192 total numeric features (168 BRDB, 24 JPDB); nested observations correlated. 2024-only standardization, L2=1 summed race NLL, deterministic conditional race-softmax, 302 training races. Optimization converged (BRDB 8 iterations, JPDB 8, BOTH 9; max gradients <=2.71e-8). Uniform baseline 1/field size, no fitted coefficient. Holdout labels cannot change training. Identical field population and probability normalization across all four models. No post-result hyperparameter or feature selection.

2025 broad coverage (usable cells per 3910 declarations): sire 2723, BMS 2163, individual pair 1001, lineage pair 3905, same-dam eligible first/early 2268, maternal aunt/uncle first/early 1458. JPDB A1 all 3879 (19 zero, 12 unresolved), surface 3874, venue/surface 3688, exact surface/distance 3729. A1 broad sire unavailable 1159/no sample 28; BMS 1730/17; pair 2439/470; lineage 0/5. Relation missingness and first-start unresolved counts remain separate. Coverage is not skill or incremental performance.

## Holdout result

| Model | Mean winner race NLL (lower better) | Entry Brier (lower better) | Top1 win rate |
|---|---:|---:|---:|
| Uniform | 2.5498953 | 0.0690453 | 6.803% |
| BRDB | 2.5756530 | 0.0698005 | 13.605% |
| JPDB | 2.3069821 | 0.0661601 | 22.109% |
| Both | 2.4439414 | 0.0687334 | 22.109% |

Uniform top1 tie resolved by smallest horse_no, not a meaningful probability discrimination result. BRDB NLL worse by 1.01%; JPDB improves 9.53%; combined improves 4.16% relative to uniform but deteriorates versus JPDB alone. Same top1 rate does not mean same selected horses. Brier also favors JPDB.

| Fixed subgroup | Races | Entries | Uniform NLL | BRDB | JPDB | Both |
|---|---:|---:|---:|---:|---:|---:|
| H1 | 76 | 1087 | 2.6328217 | 2.7760583 | 2.3604784 | 2.5547382 |
| H2 | 218 | 2823 | 2.5209852 | 2.5057870 | 2.2883320 | 2.4053150 |
| Turf | 197 | 2508 | 2.5003278 | 2.5311835 | 2.2217305 | 2.3881959 |
| Dirt | 97 | 1402 | 2.6505635 | 2.6659674 | 2.4801219 | 2.5571565 |

Day-cluster paired bootstrap, 79 observed holdout days, 2000 draws seed 20261124; descriptive percentile 95% intervals, not independent-horse inference or multiplicity-adjusted confirmatory significance.

| Contrast (negative improves) | Delta NLL | 95% interval |
|---|---:|---|
| BRDB - Uniform | +0.0257577 | [-0.0783950, +0.1353983] |
| JPDB - Uniform | -0.2429133 | [-0.3250003, -0.1588436] |
| Both - Uniform | -0.1059539 | [-0.2251088, +0.0139822] |
| Both - BRDB | -0.1317116 | [-0.2064310, -0.0532214] |
| Both - JPDB | +0.1369593 | [+0.0541613, +0.2263045] |

Fixed calibration bins retained for all models/subgroups in receipt. JPDB overall: predicted 0–5% (n1939 mean .03170 vs .02991 observed), 5–10% (1150, .06917/.08348), 10–20% (587, .13290/.14310), 20–30% (124, .24063/.14516), 30–50% (98, .38869/.34694), 50–100% (12, .58751/.33333). Higher probability bins are sparse and overconfident here; no calibrated production claim.

**Interpretation:** JPDB has a measurable retrospective advantage against the deliberately weak uniform baseline in this cohort; confounding by rider assignment, horse quality, stable and selection persists. No support for incremental BRDB with this fixed specification, including all broad/fine blood lanes and relatives. A high-dimensional correlated blood block relative to 302 training races, uneven identity coverage, small samples and distribution change may contribute; this is a hypothesis, not a demonstrated cause. Do not retrospectively change the protocol, shrink/reweight blood until holdout improves, or discard negative findings. Alternative reduced/regularized blood representations and independently held-out replication may be investigated under A3/A5 or D, not backdated B7 acceptance. Does not invalidate prior M6-R different population/baseline, prove a causal rider effect, or measure actual RaceNote improvement. Neither published prediction nor Confidence uplift is justified.

## Validation and artifacts

- All pinned sources verified; exact target/field/source and temporal checks, outcome only in label/evaluation boundary. 252544 cells strict history max_date < target_date. B4 audits reused. Independent direct SQL/Python source reconciliation fixed first/last field of each year: 64 declarations, 1536 blood + 256 rider + 256 relative = 2048 cells, all exact counts/date matches.
- B7 tests 9/9 PASS (8 synthetic, 1 actual output); B1–B5 regression 27/27, B6 15/15 per date ×2 = 30/30. Synthetic tests include actual/planned separation, same-day rejection, missing/unresolved separation, holdout labels cannot change fitted model, fixed ridge optimization, normalization and source hash gate. First run numerical results unchanged after addition of independent audit. Two audited full executions byte-identical all three outputs; private Library readback all three byte-identical. No GitHub CI claim.
- `research/run_brdb_b7_local.py` SHA256 bf39fd23934b5601d0ed7ae4709c2e87e1bbec518a3620b7d0c3df6ff328df20
- `research/audit_brdb_b7_local.py` SHA256 6855ce773230a80b66ae8135e8f094a5951f4893cd061b556af1059ce378ee51
- `research/test_brdb_b7_research.py` SHA256 d2505ce23a608112c9fe4ea5dd3380798c61a495345d7cc4747b869e65f7dbc0

Private Library /BRDB/Development_B7_20261124/:
- PRIVATE_b7_cells.csv.gz 88774fceaa81ece2045c39fc7b725cab072c31474a69e880cfda7be8945d41fc
- PRIVATE_b7_predictions.csv.gz 4700dd3b7ed3482cbcf5e013cdfc806caf637d4e6c4a58d6391cb205f0e31eb3
- b7_receipt.json fc621209b685f0ce1401c31fb185a453cfdd992e9924e1dcd375539f1344e885
- source copies and test/regression logs. Horse-level data and model outputs are private only, not Git.

Reproduce with B3 verified private input layout and JPDB nine exact SHA-named assets:
    PYTHONPATH=tools/data-storage python horse-racing/brdb/research/run_brdb_b7_local.py --input-root /private/input --jpdb-assets /private/jpdb --output-dir /private/out
    BRDB_B7_OUTPUT=/private/out PYTHONPATH=tools/data-storage:horse-racing/brdb/research python -m unittest test_brdb_b7_research -v

B1–B7 complete as research. No scoring admission. A2 next uncompleted sequential blood discovery task (condition change), A3/A4/A5 then distinct replication; C3 real modal device/visual validation and D1 broader research design remain separate. D2–D5 actual RaceNote/combined comparisons must preserve B7 negative result rather than claim B7 as production value. No merge, production, freeze, pointer change or Issue closure.

# BRDB P1-1 — lineage × race-condition descriptive research (2026-11-02)

**Status:** Local full 2016–2025 descriptive research PASS. GitHub integration is a draft candidate, not approved for prediction or CURRENT.

## Input, strict scope
- Upstream: P0-2 private descriptive mart, 481,627 KYI×SED race declarations (2016–2025), SHA-256 `0de9a6f25fd9a6295b3133c64cb276f442cfd6cc797ca6477bc7b273f0a5172c`.
- This SHA is a reproducibility *check*, not a permanently valid mutable pointer. The source generation must be retrieved independently and verified; never guess a Drive file ID.
- 477,650 **normal finishers** used as universe for conditional rates (NOT all actual starters). Abnormal/withdrawal statuses remain outside denominators, not silently classified as actual starters.
- 4 missing 2025 BRDB static profiles; historical selected pedigrees **NOT as-of-safe**. `STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED` guard required for ALL rows.
- Independent versioned study only, no modification of P0-2 BRDB CURRENT, PWA, RaceNote, Newspaper, Blood Review v0.1.

## Research design
- SIRE and BMS separate; official JRDB **lineage codes**, not estimated ancestor identities or inferred regional roots.
- Grouping: lineage role × lineage code × surface × distance band × venue code × class code.
- Distance bands: LT1400; 1400–1799; 1800–2199; GE2200. Unknown maintained separately. Surface, venue and class codes preserved rather than guessing human labels.
- Report registration entries, unique horse count, observed race years, normal finishers, wins and top-three normal finishers; direct ratios; Wilson 95% descriptive ranges.
- Baseline = **all normal finishers under exactly the same surface × distance band × venue × class**, including that lineage; no false independent-control inference.
- Baseline lift = group's rate divided by the matched-condition baseline rate (undefined where baseline is zero). No significance or predictive claim.
- Descriptive eligibility filter: n≥100 **normal finishers** and ≥3 distinct observed years; still NOT a validation certificate.

## Full local run result
- Input SHA check: PASS.
- 481,627 cohort rows validated; 477,650 normal finishers.
- 18,367 lineage × condition groups total.
- 1,935 groups pass the *descriptive sample* filter: 948 SIRE, 987 BMS.
- Local three regression tests PASS with DuckDB 1.2.2. Common Data Storage package pins DuckDB 1.1.3: qualification still pending.
- `lineage_conditions_all.csv` SHA `707c43343cadd9578dbee8f5e16d8bbf0b421d9ef69b26ef76be00dcac6c1bad`
- `lineage_conditions_eligible.csv` SHA `331f873075fc11c63cb4818e3ef7d7d1fc3fa553e7d34c3fd60e3d8ffa2d7af7`
- `baseline_surface_distance.json` SHA `81419a93ae02de85d5a3de2a54e9d76cb9ed411fb191f7ac6c9f3d1bb102f822`
- Research outputs are available in the private GPT handoff ZIP; proprietary upstream row-level mart never committed to public GitHub.

## Scientific limitations / acceptance gates
1. Low sample and denominator safeguards do **not** correct multiple comparison bias across 18,367 groups. Never sort by raw lift to produce betting picks.
2. Repeated racing by individual horses makes elementary Wilson intervals overly optimistic; treat as descriptive indicators, not independent-sample confidence certification.
3. The same cohort is used to choose and assess patterns. Temporal holdout, target leakage checks, and horse-level clustering remain future research.
4. The lack of historically observed pre-race profile means this is **NOT a valid predictive backtest**. Official lineage static match does not establish historical feature availability.
5. Confirm starter/abnormal categories against canonical JRDB semantic master, not the mere normal-finisher flag.
6. Confirm branch test on pinned DuckDB 1.1.3 and independent SHA-equivalent run before merging or a release; record the output hashes from that separate run.
7. The upstream P0-2 PR #2340 is Draft; this P1-1 change intentionally depends on it and MUST be reviewed/merged in dependency order.

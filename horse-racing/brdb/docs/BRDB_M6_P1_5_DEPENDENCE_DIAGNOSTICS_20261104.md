# BRDB M6 / P1-5 — 2026 Outcome Cohort Dependence Diagnostics (2026-11-04)

## Status and scope

**Local research-only descriptive audit PASS. Predictive evidence / Blood Score / CURRENT promotion: HOLD.**
This study checks how uncertainty in *outcome-data completeness* changes when the 2026 14-day cohort is resampled by **calendar day, race and horse**. No sire/BMS condition hypotheses, betting predictions or future-period performance estimates are produced. The original source availability remains **Drive pre-calendar-day storage only**, not an independently proven JRDB pre-race distribution of the same bytes.

## Input identity

- Accepted P1-4d `private_outcome_cohort.csv`: SHA-256 `86e78c096346a8fa79192afcf620e1dc12e895badd84a05b13b68c95a740749e`; row-level data is private, not committed.
- Accepted P1-4d `outcome_aggregate_audit.json`: SHA-256 `0483eb80a7fdaf810beec5f726445d053610257528c7cca1b1e5bd040814b42c`.
- Both inputs are pinned by expected SHA. Complete 14-date, 4,945-entry canonical keys, SED abnormal/finish semantics, KYI/SED source SHA and daily aggregates are fail-closed checked before any statistics.
- `src/audit_brdb_m6_2026_dependence.py` uses Python standard library and fixed deterministic pseudorandom seed `260914`, `2,000` replicate cluster-pairs draws per metric and dimension.
- Private aggregate output `p1_5_dependence_aggregate.json` SHA-256 `431f7568752d1a4a2f6c0d69bc0439c8ba854e5b441d9ca4497a0d9fa7e050a7` from local initial replay. A matching committed-source rerun is an additional acceptance check.

## Observed cohort and endpoints

| Item | Observed |
|---|---:|
| KYI declarations | 4,945 |
| Actual starters | 4,932 |
| Normal finishers | 4,919 |
| SED race-stopped (`abnormal_code=3`) | 13 |
| Cancellations + exclusions | 13 |
| Racing days | 14 |
| Races (date × race_key) | 372 |
| Distinct horses | 3,970 |
| Horses with repeated declarations | 906 |
| Extra repeated declarations | 975 |

These are **different denominators**. Starter rate divides by all KYI declarations. Race-stopped incidence divides by actual starters. `abnormal_code=3` is not a prediction target authorized by this audit and is not equivalent to all categories of non-normal finish.

## Three separate, one-way cluster bootstrap analyses

For each metric separately, resample the *entire set of date, race or horse clusters with replacement*, preserving numerator/denominator within sampled clusters. The percentile limits are from 2,000 deterministic draws. Cluster dimensions are analyzed **one at a time**; they are **not** a simultaneous multiway dependence correction.

| Metric | Point | Calendar-date cluster 95% interval | Race cluster 95% interval | Horse cluster 95% interval |
|---|---:|---:|---:|---:|
| Actual-starter rate (4932/4945) | 99.7371% | 99.6133–99.8559% | 99.5942–99.8606% | 99.5926–99.8774% |
| Race-stopped rate (13/4932) | 0.2636% | 0.1536–0.3786% | 0.1223–0.3984% | 0.1231–0.4227% |

The 13 stopped events occur across **9 of 14 dates, 13 races and 13 unique horses**. The limits are exploratory resampling ranges, not a guarantee of nominal population coverage. In particular the small number of dates and sparse events limit reliability.

## Constraints and next steps

1. **P1-5 statistical tooling: PASS as a descriptive uncertainty diagnostic only.** No probabilistic significance of blood-lineage suitability has been established.
2. The 14 dates are not independent calendar years. Horse repeat occurrence, race competition and day-level shared variation are structurally non-independent. Separate one-way bootstraps show sensitivity but **do not jointly account for all three levels**.
3. For genuine predictive P1-5, freeze as-of-attested blood features and a predeclared estimand; consider race/horse multiway dependency with year/day block robustness, a calibrated sparse-event method, and a sufficiently broad independent date span.
4. P1-6 walk-forward and P1-7 value over non-blood baselines **remain HOLD**: this cohort supplies only 2026 observation dates and source distribution time is unverified.
5. Do not change BRDB CURRENT, BloodReview v0.1, RaceNote, PWA, Newspaper, or any prediction/betting logic; no private JRDB row-level files are published to GitHub.

## Reproduction

```bash
python horse-racing/brdb/src/audit_brdb_m6_2026_dependence.py \
  --cohort <PRIVATE_P1_4D_OUTCOME_CSV> \
  --cohort-sha256 86e78c096346a8fa79192afcf620e1dc12e895badd84a05b13b68c95a740749e \
  --accepted-audit <PRIVATE_P1_4D_AGGREGATE_JSON> \
  --accepted-audit-sha256 0483eb80a7fdaf810beec5f726445d053610257528c7cca1b1e5bd040814b42c \
  --out <PRIVATE_P1_5_OUTPUT_DIR> \
  --repetitions 2000 --seed 260914

python -m unittest discover -s horse-racing/brdb/tests \
  -p 'test_audit_brdb_m6_2026_dependence.py' -v
```

Private source rows must not be uploaded to public GitHub Actions; CI runs synthetic fixtures only.

## Committed-source regression validation

- GitHub source commit `968b185bc87468e1ab7764e412fd965e1b1bc3ea`.
- [Actions run 41776929226](https://github.com/yukki0113/GPT/actions/runs/41776929226): `run` job `completed/success`, DuckDB 1.1.3, PyArrow 25.0.1, artifact `data-storage-fallback-41776929226` exists.
- Four synthetic tests PASS: deterministic full fixture with repeat horse IDs, pinned-input SHA tampering denial, duplicate identity denial, invalid SED outcome/actual-starter flag denial.
- Actions tests use synthetic fixtures only, not licensed JRDB rows. Real 4,945-row original private input audit and aggregate output completed locally. GitHub CI PASS is independent from the private real-data replay.

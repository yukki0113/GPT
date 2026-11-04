# BRDB P1-2 — 2016–2025 年次安定性の記述監査（2026-11-04）

## Status and limitations

**Formal P1-2 research-only descriptive acceptance: PASS.** This is an accepted year-stratified *descriptive* audit, not a claim of forward predictive stability. This audit describes year-stratified data support; it does **not** prove predictive stability or promote historical static pedigree to a pre-race as-of feature.

## Input identity

- P0-2 verified committed-code replay mart `brdb_result_mart.parquet`, SHA-256 `8b41f4b7132bc268428133535cce9c4aff79ac5b7b4c0dca5a5cdd5c1df13b63` (481,627 rows).
- P1-1 verified eligible `lineage_conditions_eligible.csv`, SHA-256 `331f873075fc11c63cb4818e3ef7d7d1fc3fa553e7d34c3fd60e3d8ffa2d7af7` (1,935 unique groups).
- Runs under DuckDB 1.1.3; source code is `src/build_brdb_annual_stability_report.py`.

## Method

For each P1-1 eligible lineage-role × lineage-code × surface × distance-band × venue × race-class group, output its 10 annual cells (2016–2025). Calculate `entries`, normal-finisher denominator `n`, wins, top3 and corresponding **same-year, same-condition all-normal-finishers** baseline. An annual cell is only used for descriptive direction checks when the lineage group has `n >= 10` and condition-year baseline `n >= 50`. These are exploratory coverage thresholds, not inferential acceptance criteria. Missing years remain `LOW_SAMPLE`, not zeros evidencing poor aptitude.

Rows and lineage identifiers remain in private output `eligible_group_years.csv`; this GitHub document contains only aggregates.

## Observed full-cohort results

| Measure | Result |
|---|---:|
| P1-1 eligible lineage condition groups | 1,935 |
| Group × year cells | 19,350 |
| Cells meeting exploratory support thresholds | 15,665 |
| Groups with >=3 supported years | 1,866 |
| Groups with >=5 supported years | 1,782 |
| Groups with 10 supported years | 822 |
| Groups with 0 supported years | 36 |
| Supported annual cells with win rate ABOVE same-year baseline | 7,480 |
| Supported annual cells with win rate BELOW same-year baseline | 8,132 |
| Supported annual cells with top3 rate ABOVE baseline | 7,701 |
| Supported annual cells with top3 rate BELOW baseline | 7,885 |

Some annual cells tie the baseline and are omitted from the ABOVE/BELOW counts. Yearly cells **do not provide independent confirmations**: repeated starts, condition heterogeneity and selection on the same 10-year sample all remain. An apparently favorable group in-sample is not an established future signal.

Independent invariant: summing `entries`, `n`, `wins`, `top3` over the 10 annual cells reproduces the P1-1 original CSV for **all 1,935 groups (0 differences)**.

## Determinism and tests

- Local DuckDB 1.1.3 full-data run: `PASS`.
- GitHub Actions [BRDB research PR tests #41755843294](https://github.com/yukki0113/GPT/actions/runs/41755843294): `success` at source head `ab9368b5d4fb31d85ff685fedc453ca295101096`, DuckDB 1.1.3; P0-2, P1-1 and P1-2 suites PASS.
- Earlier import-path CI failure [#41755701093](https://github.com/yukki0113/GPT/actions/runs/41755701093) was fixed and revalidated.
- Synthetic-only unit tests: **4/4 PASS**; verify 481,627-row generated positive cohort, deterministic repeated output, input SHA fail-closed, support threshold fail-closed, malformed P1-1 selected cohort rejection.
- Private annual CSV SHA-256: `ba9342b81d9554b34611fb9f2123e95c6110ae3fcf1610f7e6f52598bc72a699` (not distributed through the public GitHub repository).
- Output summary: `annual_stability_summary.json`, does not include horse/lineage/year rows.

## Acceptance boundary and further work

- `research_only=true`, `prediction_safe=false`, `pedigree_temporal_status=STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED`.
- `normal_finisher` is **not** actual starters; no automatic betting ranking, as-of backtest, CURRENT, PWA, RaceNote or Newspaper publication.
- The annual cells are descriptive and selected on the same years. Before a claim of predictive value, require independent later-period validation, multiplicity control, horse-level clustered uncertainty, temporal source attestation and actual-starter denominator work.
- Main source of truth remains the P0-2 / P1-1 formally accepted code. P1-2 is an independent research-stage add-on, not a modification of those results.
# 20261006_007 — Resume frozen PEDIGREE_CROSS 5y

- Status: **DONE — canonical 5y stages accepted**
- Decision: **`PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY`**
- Production impact: **NONE**

## Provenance and local preflight

The execution source for canonical planning, C1, DuckDB C2A, and C2B was reviewed main commit `24c4d2b410ed27b663d4a7d618754ae0dbe745c0`. The bounded exact-ID/R1 label reporter used separate analysis commit `c1b2b8eb06e956f3ec69d698c60c56d848f53ba9`; it did not change the canonical stage code or parameters.

The required `python -m unittest horse-racing/jrdb/tests/test_jrdb_edge_v04_family_preflight.py` passed (3 tests). Local Data Storage `check-deps` returned `DEPENDENCY_MISSING` for DuckDB and PyArrow. One normal requirements install failed because the managed proxy connection was denied; the post-install check remained missing. The documented Actions fallback was used. Python was 3.12.14; Actions installed DuckDB 1.1.3 and PyArrow 25.0.1.

Immutable input artifacts were verified before the research run:

| Input | Run / artifact | Extracted SHA-256 | Rows |
|---|---|---|---:|
| Feature Mart | `36116777782` / `jrdb-edge-feature-mart-parquet-36116777782` | `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6` | 781,161 |
| Stage B catalog | `36262821119` / `jrdb-edge-v04-stage-b-36262821119` | `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba` | 47,371 |

The Feature Mart's accepted conversion audit confirms 781,161 source/target rows; Stage B's accepted audit confirms 47,371 catalog templates. The extracted Parquet bytes matched the pinned hashes. The baseline is the canonical 3y fallback run `37321021557`.

## Actions chain

| Stage | Issue | Run | Artifact | Archive digest |
|---|---:|---:|---|---|
| Family plan, C1, C2A | [#1811](https://github.com/yukki0113/GPT/issues/1811) | [37405197661](https://github.com/yukki0113/GPT/actions/runs/37405197661) | `data-storage-fallback-37405197661` | `sha256:e82a5a06aeb1346e21ed689222543bf8435f86e7135573a9abc2eb42baf834cf` |
| C2B exact metrics | [#1812](https://github.com/yukki0113/GPT/issues/1812) | [37405567334](https://github.com/yukki0113/GPT/actions/runs/37405567334) | `data-storage-fallback-37405567334` | `sha256:6bccbc8fb7d61564c04cd27aa413869ba3df5ed4b138db08d38fde38fbb2849e` |
| Exact IDs and comparison | [#1815](https://github.com/yukki0113/GPT/issues/1815) | [37406173544](https://github.com/yukki0113/GPT/actions/runs/37406173544) | `data-storage-fallback-37406173544` | `sha256:87aac5e9ebed09d3e73080bae804052a58d6c5f497c04a9210be29cc55d4b35e` |

All three final fallback audits were PASS. The first reporting request, [#1814](https://github.com/yukki0113/GPT/issues/1814), failed only because its argv omitted the `r1_wave_a_3y_canonical/` directory inside the baseline artifact; the failed-step stderr was inspected and #1815 corrected that path. It did not rerun C1 or C2.

## Frozen family plan and canonical stages

- Window: `2020-12-28 .. 2025-12-28` inclusive; years 5.
- Selection: `--family PEDIGREE_CROSS`, the three specified Wave A lanes, depths 2–3, original full catalog. Result-blind family selection was audited before C1.
- Selected templates: **520**, all `PEDIGREE_CROSS`; baseline/interactions **456/64**; depth 2/3 **64/456**. `TRANSITION_PRIORITY` contributed zero templates for this family.
- Sorted template-ID SHA-256: `7dc37515ae01a5e791a2e48f5db3bb3583fb1cb3e08456b7a1f37def734b86d9`.
- Shards: **4**; plan SHA-256: `a7e1aea22348f4d8845041d4811e13c03db5afb39ab4401b51dcc65719587f36`.
- C1 shard counts: baseline D2 **3,603**, baseline D3 **32,322**, interaction D2 **361**, interaction D3 **5,995**. All shard audits PASS with identical input/catalog/plan SHA, 5y window, ROI 110/105, max 100/template, and unchanged support floors. Merge PASS, **42,281** unique candidates, zero duplicate candidate IDs.
- Canonical DuckDB C2A PASS: **9,022** shortlisted, all `ESTABLISHED_CURRENT`; D2 baseline/interaction **731/93**, D3 **6,958/1,240**. Immediate child-parent links **26,242**, unique parent requests **9,105**, total exact metric requests **17,350**.
- C2B: all **16** shard audits and merge PASS. Feature hash and 5y window agreed; missing value branches **0**. Request Parquet SHA-256 `a1a0eab53eb534651c4304d94ab7912ea1505cf1c68d48912ce4d1aec52d8e6f`. The full request/result ID sets were checked: **17,350/17,350**, missing **0**, extra **0**, duplicates **0**; enriched C2 count **9,022**.
- No threshold, support-floor, SQL predicate, market conditioning, or production setting changed.

## Canonical 3y versus frozen 5y

Counts and rates below use each family's C2 count as denominator. The 3y baseline is `PEDIGREE_CROSS` from accepted run `37321021557`.

| Metric | 3y | 5y |
|---|---:|---:|
| C1 candidates | 41,012 | 42,281 |
| C2 shortlist | 11,963 | 9,022 |
| Incremental | 266 (2.22%) | 266 (2.95%) |
| Mixed | 68 (0.57%) | 64 (0.71%) |
| Jackpot-dependent | 11,629 (97.21%) | 8,691 (96.33%) |
| Incremental depth 2 / 3 | 30 / 236 | 22 / 244 |
| Incremental child support median | 50 | 62 |
| Incremental recent 365d / 730d support median | 21 / 38 | 16 / 32 |
| 365d win / place positive direction | 209 / 184 | 210 / 173 |
| 730d win / place positive direction | 231 / 223 | 240 / 202 |
| 730d/full direction contradiction | 2,304 | 2,309 |
| One-year confinement | 153 | 132 |
| No 365d support | 53 | 70 |
| Top3 exclusion removes both lanes | 11,629 | 8,691 |

Incremental child support min/p10/median/p90/max was **16/23/50/161/683** in 3y and **16/25/62/206/1,202** in 5y. Across all immediate-parent ROI comparisons attached to incremental candidates, min/median was **−117.21/89.25** in 3y (1,536 comparisons) and **−120.84/90.23** in 5y (1,552 comparisons). The summary includes parent ROI and rate deltas for the 10 strongest bounded examples in each window, explicitly labelled as examples rather than population estimates.

Of the 15 candidate IDs retained as bounded 3y examples, **12** appear in 5y C1 and **11** in 5y C2. Full overlap, additions and removals cannot be reconstructed because the 3y artifact does not retain full candidate IDs. The 3y C2A audit covers all families, so its child-parent links, parent-request count and request count are not family-only comparators. No composite score was introduced.

## Decision and disposition

**`PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY`.** The non-jackpot incremental count remained 266 and the C2 incremental rate rose. Yet 96.33% of the 5y shortlist is top3-sensitive, recent support medians declined, and full individual-candidate continuity is unavailable. These results support observing the current family; they do not authorize depth 4 or another expansion. The bounded examples are research evidence, not betting recommendations.

PR #1809, the earlier pre-evaluation blocker record, was confirmed **closed**; its result file was absent from main. This result and the bounded `r1_summary.json`, `r1_report.md`, and 100-row `shortlist.csv` are proposed in PR #1813. Full C1/C2 tables and exact metric shards remain in Actions artifacts only. No PR was merged automatically.

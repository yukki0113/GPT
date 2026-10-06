# PEDIGREE_CROSS frozen 5y evaluation

Status: `CANONICAL_PEDIGREE_CROSS_5Y_EVALUATED`  
Decision: `PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY`  
Production impact: NONE

Canonical C1/C2A/C2B source: `24c4d2b410ed27b663d4a7d618754ae0dbe745c0`. Exact ID and R1 label analysis source: `c1b2b8eb06e956f3ec69d698c60c56d848f53ba9`. Window: 2020-12-28 through 2025-12-28 inclusive.

## Frozen selection and canonical stages

The full Stage B catalog selected 520 `PEDIGREE_CROSS` templates: 456 baseline and 64 interaction, with D2/D3 counts 64/456. Four C1 shards passed. Sorted template-ID SHA: `7dc37515ae01a5e791a2e48f5db3bb3583fb1cb3e08456b7a1f37def734b86d9`. Plan SHA: `a7e1aea22348f4d8845041d4811e13c03db5afb39ab4401b51dcc65719587f36`.

C1 returned 42,281 unique candidates. Canonical DuckDB C2A shortlisted 9,022, all via `ESTABLISHED_CURRENT`. There were 26,242 immediate child-parent links, 9,105 unique parent requests, and 17,350 total exact metric requests. All 16 C2B shards and the merge passed. Request/result ID sets were equal: 17,350 each, with no missing, extra, duplicate, or missing-value branches.

## Three-year to five-year comparison

| Measure | 3y canonical | 5y frozen family |
|---|---:|---:|
| C1 candidates | 41,012 | 42,281 |
| C2 candidates | 11,963 | 9,022 |
| Incremental | 266 (2.22%) | 266 (2.95%) |
| Mixed | 68 (0.57%) | 64 (0.71%) |
| Jackpot-dependent | 11,629 (97.21%) | 8,691 (96.33%) |
| Incremental D2/D3 | 30/236 | 22/244 |
| Incremental child support median | 50 | 62 |
| Recent 365d/730d support medians | 21/38 | 16/32 |
| 730d/full direction contradiction | 2,304 | 2,309 |
| One-year confinement | 153 | 132 |
| No 365d support | 53 | 70 |
| Top3 exclusion removes both lanes | 11,629 | 8,691 |

Incremental support distribution (min/p10/median/p90/max): 3y 16/23/50/161/683; 5y 16/25/62/206/1,202. Immediate-parent ROI deltas across incremental comparisons had 3y min/median −117.21/89.25 and 5y −120.84/90.23. The strongest 10 bounded examples in each window have parent rate deltas in `r1_summary.json`; those example distributions are not population estimates. The 365d win/place positive-direction counts were 209/184 in 3y and 210/173 in 5y; 730d counts were 231/223 and 240/202.

Among the 15 baseline example IDs available in the bounded 3y artifact, 12 appear in the 5y C1 set and 11 in the 5y C2 set. Full overlap/addition/removal counts cannot be calculated because the 3y artifact does not retain all candidate IDs. Its C2A audit recorded parent links and requests across all families, so family-only 3y totals for those fields are unavailable.

## Decision

The non-jackpot incremental count holds at 266 and its C2 rate rises, while 96.33% of the 5y C2 set remains top3-sensitive, recent support medians decline, and complete candidate-ID continuity cannot be verified. This supports observation of the current family. Further design requires a separate instruction. The conditions in `shortlist.csv` are research examples, not betting recommendations.

# 20261006_008 / 009 — Complete observe-only cohort freeze

- Status / decision: **`READY_FOR_NEXT_TRUE_FORWARD_DATE`**
- Instruction 008 source: `18646e915d800edb1b075a95553470247205dec3`
- Correction instruction 009 source: `bf7ea31362554c496287cd2313b2377c71a2f4d2`
- PR: [#1818](https://github.com/yukki0113/GPT/pull/1818), updated before merge in response to the membership review comment.
- True-forward date executed: **No**. The rerun below is strictly historical reproduction. No prospective result data was opened.
- Production impact: **NONE**. No v0.2 STANDARD, v0.3 SHADOW, Edge Registry, or RaceNote/PWA serving change.

## Accepted evidence and full 3y reconstruction

The accepted 3y canonical R1 was source commit `9aba7103f944ea419189c104be4e48485b819d0d`, run `37321021557`, with result file Git blob `d27f7cdb434f8294b280151da4731fc17b917eb8`. The accepted 5y `PEDIGREE_CROSS` C1/C2A and C2B runs were `37405197661` and `37405567334`; canonical source `24c4d2b410ed27b663d4a7d618754ae0dbe745c0`, result file Git blob `68e6343d8ab42ab32401f337c834996da7d00b5f`. The 5y full-label/template export was [run 37416474375](https://github.com/yukki0113/GPT/actions/runs/37416474375), PASS, artifact `11391276365`, archive SHA-256 `b81669aeff5fa73a93bc421e3b8acf775d74f8709329132a0b06dc7eb0d6666b`, full JSON SHA-256 `b75025ff9bab80d74d3ba99170cf7661ff1c27f64c85682081fc1598569ea3df`. Its 5y summary labels, family summary, and bounded examples matched the accepted report exactly.

Local `.venv-data-storage` check was `DEPENDENCY_MISSING` for DuckDB and PyArrow. One normal pinned-requirements repair attempt could not install DuckDB under the managed network policy; the repeated check remained missing. The documented Actions fallback was used with DuckDB 1.1.3 and PyArrow 25.0.1.

The first 3y fallback attempt, Issue #1819, stopped at the accepted planner SHA guard because the current family-aware planner serializes a different plan. No candidate evaluation from that attempt was used. The accepted 3y preflight/planner implementation was pinned as `jrdb_edge_v04_preflight_3y_canonical.py` (accepted blob `f393d8851a63003d5f3070b751b09fba7ac86e69`) and `plan_jrdb_edge_v04_stage_c1_shards_3y_canonical.py` (same accepted planning logic, with only its import routed to the pinned module). Issue #1820 stopped at a wrapper syntax error before execution. Both failed attempts were discarded.

The final 3y reconstruction, [Issue #1821](https://github.com/yukki0113/GPT/issues/1821) / [run 37420322097](https://github.com/yukki0113/GPT/actions/runs/37420322097), **PASS**, source commit `a7549548949d3c5a6ae722e6defeae0edfe3ad71`, artifact `11392124793`, archive SHA-256 `86a1b2d118f7264502b53993493fb296d0bc99e6bec6895f2e651e689e87fe35`. The full 17,807-row enriched JSON SHA-256 is `5099ea48faf02fcfd0752202d9840c9491ca0fd70e29cf436cb6f01d19cd3a33`. It remains in the Actions artifact, not Git. The wrapper used the unchanged accepted R1 label classifier, verified every candidate/template ID using the canonical ID construction, and compared bounded examples and family summaries with the accepted 3y output exactly.

| Frozen reproduction guard | Required | Observed |
|---|---:|---:|
| Selected templates | 1,106 | 1,106 |
| Planner SHA-256 | `de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8` | identical |
| C1 merged candidates | 68,685 | 68,685 |
| C2A shortlist | 17,807 | 17,807 |
| Child-parent links | 52,171 | 52,171 |
| Unique parent requests | 14,129 | 14,129 |
| Exact metric requests/results | 30,733 / 30,733 | 30,733 / 30,733; identical ID sets |
| Incremental / mixed / jackpot labels | 367 / 90 / 17,350 | 367 / 90 / 17,350 |
| Incremental PEDIGREE_CROSS / PEDIGREE_TRANSITION_CROSS / TRANSITION_CROSS | 266 / 81 / 20 | 266 / 81 / 20 |

Frozen inputs remained Feature Mart run `36116777782`, SHA-256 `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`, and Stage B run `36262821119`, catalog SHA-256 `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`. The window was `2022-12-28 .. 2025-12-28`, as-of `2025-12-28`, original three Wave A lanes, depths 2–3, win/place ROI 110/105, original support floors, and max 100 per template. No search expansion, threshold change, or classifier change occurred.

## Corrected cohort membership

PR #1818 originally included ten ranked `PEDIGREE_TRANSITION_CROSS` examples. Those examples are presentation evidence only. The corrected builder reads the complete reproduced 3y enriched population and includes **all 81** eligible definitions. All ten presentation examples are contained within those 81; they have no selection role.

| Family | Source | Incremental source members before dedup | Frozen matcher rows |
|---|---|---:|---:|
| `PEDIGREE_CROSS` | Accepted 5y full enriched | 266 | 266 |
| `PEDIGREE_TRANSITION_CROSS` | Reproduced accepted 3y full enriched | 81 | 81 |
| `TRANSITION_CROSS` | Stopped family | 0 admitted | 0 |
| **Total** | | **347** | **347** |

- Exact condition duplicates: **0**; semantic ordering/serialization duplicates: **0**; duplicate-map entries: **0**. The builder preserves all represented candidate/family/source provenance per matcher row if future evidence reveals a cross-family duplicate.
- Frozen config: `horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json`; metadata: `horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_source_v0_1.json`.
- Fingerprint-set SHA-256: **`ad0cf386601fb0366db27197072205c565eef189fa2e1062a97702f4b30f4876`**.
- Cohort file SHA-256: **`c93b4e4f7f899e42eb94738603ce0bbe2f7ac092da43528e42d83cbdc776da71`**.
- Every row has a verified candidate/template identity, unique canonical condition fingerprint, `OBSERVE_ONLY`, and `production_eligible=false`. Historical metrics are audit-only. Market/popularity do not affect membership. No rank, top-N, or presentation selection is applied.

## Prospective machinery and tests

- Canonical 3y reproduction/export: `horse-racing/jrdb/src/reproduce_jrdb_edge_v04_3y_full_enriched.py`.
- Cohort builder/validator: `horse-racing/jrdb/src/jrdb_edge_v04_observe_cohort.py`. It fails closed unless full 5y and 3y label totals, family counts, 347 eligible source rows, and every candidate/template identity match the pins.
- Pre-race matcher, freeze writer/validator, post-result evaluator: `horse-racing/jrdb/src/jrdb_edge_v04_observe_shadow.py`. The matcher uses the canonical Stage C1 dimensions and string equality, ignores market/popularity, rejects result fields, and retains overlapping raw matches. A timezone-aware pre-result freeze manifest hashes both the cohort and fact source. Post-result evaluation requires a PASS freeze and later result-open timestamp, joins normal JRDB results by date/race/horse, and reports raw and unique-horse views. Overlapping ROI is non-additive.
- `python -m unittest discover -s horse-racing/jrdb/tests -p 'test_jrdb_edge_v04_observe_shadow.py'`: **9 tests passed**. They cover complete 347/266/81 membership, rejection of bounded presentation input, exact and semantic duplicates with cross-family provenance, candidate-ID duplication guard, fingerprint stability, cohort immutability, leakage rejection, market independence, repeated freeze determinism, raw overlap, unique-horse evaluation, and result-open timing. The actual 347-row cohort was built and validated separately.

No clean unseen race-day fact snapshot was available, so no true-forward freeze or result evaluation was run. The future review gate remains descriptive: multiple distinct race days, independent hits where applicable, meaningful support, no single-payout domination, interpretable parent/context logic, and no material contradiction of the historical direction. No promotion threshold or production decision is made here.

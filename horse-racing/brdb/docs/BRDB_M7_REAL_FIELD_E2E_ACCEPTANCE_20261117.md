# BRDB M7 real PACI full-field ①–④ + D4 research E2E acceptance — 2026-11-17

Status: **RESEARCH FULL-FIELD E2E PASS / M7 PRODUCTION PROMOTION NOT AUTHORIZED**.
Tracker: [#2628](https://github.com/yukki0113/GPT/issues/2628). M6 [#2395](https://github.com/yukki0113/GPT/issues/2395) remains **OPEN/BLOCKED**.

## Purpose and source of truth
Verify the already implemented ① sire, ② broodmare-sire, ③ JRDB official sire-line × BMS-line, ④ guarded maternal relatives, and accepted D4 supplemental research sidecar on the **same 2026-11-15 real PACI race**, through v0.2 candidate and v0.3 candidate contracts. No prediction, scoring, factor generation, CURRENT mutation, RaceNote or PWA publication.

Repository `yukki0113/GPT` `main` contains the canonical modules; [PR #2630](https://github.com/yukki0113/GPT/pull/2630), merge `9407c0f732283ccd417a88feaba1758dff3eaf91`. The exact source files were transferred by audited source-only handoff [#2632](https://github.com/yukki0113/GPT/issues/2632), run [44048195464](https://github.com/yukki0113/GPT/actions/runs/44048195464), pinned source checkout `78c6e528b4ab5c4612185d8c91737e19d1e9a65a`, 16 file SHA manifest checks PASS. This second handoff fixes the missing canonical `jrdb_ukc.py` dependency in first source-only attempt [#2631](https://github.com/yukki0113/GPT/issues/2631). Source transport itself contains **no horse-level data**.

## Canonical inputs and validation

| Asset | Accepted identity / SHA-256 | Gate |
|---|---|---|
| Real PACI | `PACI261115.zip`; `3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050` | original canonical Drive bytes, ZIP CRC, BAC/KYI/UKC parser, 18/18 |
| Race | `05265412`, 2026-11-15, 18 declarations | race/horse_id/horse_no exact match |
| JRDB Analysis | v1.4 `analysis-v1_4-postrace-20261101-01` | recovered eleven annual Parquet partitions; canonical manifest and partition SHA verified |
| BRDB research pedigree | `5279af0bd8226cde`; source ZIP `672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4` | manifest validation PASS; `pedigree_fact.parquet` and `parent_relation.parquet` SHA verified |
| D4 fixed real-PACI sidecar | `639d6a1c19ec2fb45cffd06fb235f3b659030faa1703c941510af1251acdeefb` | fixed D3 SHA pins and exact PACI extracted context SHA `c0595775649eb03a31254093d0be6cdd703932fa45e081c7ea822193820d92a0` |
| DuckDB runtime | CPython 3.13; DuckDB 1.1.3 | exact cp313 wheel recovered from audited Actions run [41748491405](https://github.com/yukki0113/GPT/actions/runs/41748491405); local dependency installed |

D4's independently attested PACI presence before scheduled off is described in [PR #2619](https://github.com/yukki0113/GPT/pull/2619); it **does not** independently establish provider publication timing or historical D3/③/④ as-of.

## Exact repository code execution
1. Canonical `run_brdb_sire_bms_evidence.py` via `--paci PACI261115.zip --race-key 05265412 --analysis-root <verified Analysis v1.4>`.
2. Canonical `run_brdb_pairing_evidence.py` on the ①② JSON and the same Analysis root.
3. Canonical `run_brdb_relatives_evidence.py` on the same PACI, exact pedigree research generation and Analysis root.
4. New `run_brdb_m7_integrated_replay.py` with the three research outputs, immutable D4 sidecar, same exact PACI; validates v0.2/v0.3 against real Draft 2020-12 JSON Schema and uses the unchanged `brdb_integrated_review_v03_candidate.merge`.
5. Entire chain repeated **independently** on identical raw inputs with new ①②/③/④ intermediate files. Intermediate source JSON timing fields are intentionally runtime-dependent; nevertheless both resulting integrated candidate files had **byte-identical** SHA-256 across runs.

## Real-field results

| Check | Result |
|---|---:|
| PACI BAC/KYI/UKC matched | 18/18 |
| ① sire evidence entries (5 scopes × 18) | 90 |
| ② BMS evidence entries (10 scopes × 18) | 180 |
| ③ pairing evidence entries (5 scopes × 18) | 90 |
| ④ guarded maternal relative relationship entries | 75 |
| ④ horses with verified mother-root (historical as-of still unresolved) | 13/18 |
| ④ horses without a verified mother-root | 5/18, `SOURCE_UNAVAILABLE` |
| Sire/BMS aggregate availability | each: 17 `AVAILABLE`, 1 `LOW_SAMPLE` |
| Pairing availability | 18 `AS_OF_UNVERIFIED` |
| Relatives availability | 13 `AS_OF_UNVERIFIED`, 5 `SOURCE_UNAVAILABLE` |
| Zero-start evidence cells | 12; rates remained null, not 0% |
| D4 supplemental descriptive items | 66, including 4 horses with empty supplemental arrays |
| v0.2, v0.3 Draft 2020-12 JSON Schema | both PASS |
| Full-field canonical horse ID/number identity and ordering | 18/18 PASS |
| All factors, summary, confidence | empty factors; null summary; `UNASSESSED` for all 18 |
| Full chain second execution | PASS; v0.2/v0.3 byte SHA identical |
| Source-only local unit regressions | 6 identity-scaffold + 13 adapter = **19/19 PASS** |
| Exact PR CI | [BRDB run 44047329375](https://github.com/yukki0113/GPT/actions/runs/44047329375) PASS; [repository regression 44047329692](https://github.com/yukki0113/GPT/actions/runs/44047329692) PASS |

Canonical integrated output fingerprints:

- v0.2 `9ffef59d343f07a2fcacda24c8e8e0650c6c1f3d3c7e38c6f06838c7b051c0b3` (496,436 bytes).
- v0.3 `96129fdd70155cea98e07e1a5725116e6d2ade7dc3ee9f8ddf1c8a625655774f` (562,855 bytes).
- replay receipt `d6a3270254c56369f70d695b484644aed0d2f7f0d94ee3532a77376711365276`.

## Private artifacts / readback
Horse-level ①②, ③, ④, integrated v0.2, integrated v0.3 and run receipt were uploaded to **personal Library `/BRDB/M7/`** (six files), not Git. File list and metadata verified. The three integrated outputs/receipt were independently materialized from Library, then byte-compared to local originals; **all SHA readback PASS**.

## Explicit interpretation boundary
- Only non-scoring **research composition** is accepted. ①② are descriptive histories, not causal suitability. `AVAILABLE` refers to available observed sample coverage, not a positive fitness assessment.
- ③ is **historical lineage profile AS_OF_UNVERIFIED**; ④ is **profile-date checked, not historically replayed**. No `prediction_safe=true` or validated performance claim.
- ④ source has per-relative result statistics, but frozen v0.2 observation schema requires a matched condition baseline; the adapter carries **canonical relative identity / relation-type facts only** (`observations=null`) rather than fabricating a baseline. Original ④ JSON remains in private Library for future versioned non-lossy contract design.
- All 18 integrated `status=AS_OF_UNVERIFIED`; positive/negative/unknown factors remain empty, summary null, confidence UNASSESSED. D4 is observation-only.
- No blood score, probabilities, ranks, marks, automatic horse suitability, or RaceNote/PWA/Newspaper integration. Frozen `brdb-review-v0.1`, v0.2 candidate contract, BRDB CURRENT and production viewers unchanged.
- **M7 research E2E gate PASS does not mean M7 production graduation.** Remaining independent acceptance: qualified interpretation rules, non-lossy ④ contract design where needed, consumer contract regression, historical source-time scientific gates and explicit user-approved promotion. M6 [#2395](https://github.com/yukki0113/GPT/issues/2395) remains OPEN/BLOCKED.

## Next prioritized work
1. Record this real-field evidence in M7 tracker as **research E2E PASS**, without closing overall M7.
2. Audit whether the **④ per-relative scoped statistics** require a versioned additive child schema or sidecar. Do not alter frozen v0.2/v0.3 or invent zeros/baselines.
3. Design and test **qualified interpretation/consumer boundary** separately; preserve unverified states and research-only output.
4. Keep M6 as independent scientific track requiring genuine pre-off frozen paired predictions and historical as-of support.

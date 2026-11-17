# BRDB M7 ④近親条件別実績 詳細サイドカー v0.1 candidate / research-only

- Date: 2026-11-17 JST
- Status: **RESEARCH-ONLY CANDIDATE / SOURCE-CANONICAL E2E LOCALLY VERIFIED / NOT PRODUCTION AUTHORIZED**
- Tracker: [M7 #2628](https://github.com/yukki0113/GPT/issues/2628)
- Dependencies: accepted M7 real-field E2E v0.3 and canonical ④ raw producer v0.1.

## Purpose

2026-11-17のM7実PACI全18頭E2Eでは、④のcanonical近親関係の証拠75件はv0.3へ継承できたが、元研究出力の**各近親×5条件**の出走・勝ち・3着内数・3着内率は、v0.2/v0.3の`observation`が必須とする全体比較母数を元④出力が保持していないため、情報を失わずには既存contractに変換できなかった。

本追加契約は既存v0.2/v0.3を変更せず、元④出力の全JSONツリーを独立サイドカーに**ロスレス複製**する。存在しない比較母数/基準率を捏造しない。

## Artifacts

- Source adapter: `src/brdb_m7_relatives_detail_candidate.py`
- Detailed JSON Schema: `schema/brdb_m7_relatives_detail_v0_1_candidate.schema.json`
- Research-only preview: `src/brdb_m7_research_consumer_preview.py`
- Preview Schema: `schema/brdb_m7_research_consumer_preview_v0_1.schema.json`
- Fixed local runner: `src/run_brdb_m7_relatives_preview.py`
- Regressions: `tests/test_brdb_m7_relatives_detail_candidate.py`

## Preservation / identity

1. Exact `(horse_id, horse_no)` cohort, race date/key/venue/surface/distance/course and independent BRDB/JRDB generation IDs must match v0.3.
2. `source_metadata` preserves all top-level canonical ④ fields except `horses`, including `timing_ms`; `horses` preserves **all source per-horse fields** including relationship/IDs/birth/profile dates, all five `scope_stats`, `relative_counts`, and `with_relevant_starts`. `source_canonical_sha256` binds the reconstructed original JSON tree.
3. All `REL_<target horse ID>_<relative ID>_<relationship>` identities match exactly the existing v0.3 `PEDIGREE_FACT` evidence list; no fuzzy join, guessed sibling, or missing relative can pass.
4. Each relative's five scope rows must have nonnegative/consistent `starts,wins,top3`, observed rate rounded to four decimals when starts>0, and `null` rate when starts=0; any extra/missing scope fails closed.
5. `SOURCE_UNAVAILABLE` for unresolved canonical mother roots and `AS_OF_UNVERIFIED` for all identified relations remain unchanged; the source's historical relation availability has **not** been proven as-of the original racing date.
6. Zero relatives means only **no relationships observed under accepted canonical-guarded research scope**; it does not certify that no siblings exist or indicate aptitude.
7. Output is a **separate research sidecar** with `prediction_safe=false`, `no_forecast_or_score=true`, and `release_status=RESEARCH_SIDECAR_ONLY`. No changes to frozen Blood Review v0.1, v0.2, v0.3, CURRENT or PWA/RaceNote.

## Qualified interpretation / consumer regression

A separate `brdb-m7-research-consumer-preview-v0.1` emits only per-horse canonical identity, component coverage counts, and explicitly qualified reason codes. For ①②, `AVAILABLE` is labeled `DESCRIPTIVE_SAMPLE_ONLY`, not "good suitability". For ③④, only `HISTORICAL_AS_OF_UNVERIFIED` or `SOURCE_UNAVAILABLE` may be emitted. It includes no score, confidence promotion, win probability, ranking or suitability verdict. Every row is `NO_FIT_VERDICT_PERMITTED`; `production_authorized=false`.

The frozen Newspaper handoff `brdb_newspaper_handoff.project_review()` must reject both integrated candidate records and the research preview as unsupported contracts. It remains unchanged. **Preview is not a user-visible PWA or Newspaper design approval.** User review of actual intended display fields/screens and independent consumer regression are still needed before any production cutover.

## Local research E2E on fixed input — 2026-11-17

Inputs: non-public Library `/BRDB/M7/m7_integrated_v03_05265412.json` and `/BRDB/M7/m7_relatives_05265412.json` from accepted 18-horse PACI race `05265412` (2026-11-15). Original v0.3 byte SHA: `96129fdd70155cea98e07e1a5725116e6d2ade7dc3ee9f8ddf1c8a625655774f`.

- 18/18 horses, mother roots 13/18, unresolved 5/18;
- 75 canonical relative records ×5 scopes = **375** descriptive observation cells;
- **285** zero-start cells preserve `top3_rate=null`, not zero;
- v0.3 + detailed sidecar + preview Draft 2020-12 Schema all PASS;
- Two independent *composition* runs on fixed ④ source bytes: byte-identical detail and preview; full ①〜④ upstream E2E replay is established in the prior [M7 acceptance](BRDB_M7_REAL_FIELD_E2E_ACCEPTANCE_20261117.md), **not repeated in this task**;
- Local synthetic source contract tests **18/18 PASS**;
- Private detail/preview outputs and SHA receipts are kept out of Git.

Output SHA256 values are recorded in the private research receipt; publicly publish hashes and aggregates only. No `.json` horse-level results will be committed.

## Remaining graduation gates

- Actual historical lineage/relation graph as-of evidence or explicit limitation of allowable consumer uses.
- Decided user-facing text, presentation and omitted-field policy, with approval before PWA/Newspaper display.
- Cross-component consumer regression on the *actual* RaceNote/Newspaper field schema and exact identities, not this research preview alone.
- M6 prospective prediction-value scientific gate [#2395](https://github.com/yukki0113/GPT/issues/2395) remains OPEN/BLOCKED.
- **No production M7 promotion or M8 start without explicit graduation decision.**
# BRDB Phase 4 — 3–5代祖先・クロス・類似血統 v0.1

Status: RESEARCH FOUNDATION IMPLEMENTED / VALIDATION & COVERAGE EXPANSION PENDING
Date: 2026-10-22

## Boundary

Production Blood Review `brdb-review-v0.1` is frozen and unchanged. This research layer must not alter Newspaper, PWA, current Drive generation, Review score or prediction marks. Existing EdgeDB `PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY` is an independent feature-mining result **not** an approved cross/inbreeding source or predictive score.

## Implemented

`src/brdb_ancestor_graph.py` provides:

- `ancestor_graph(horse_id, relations_for, max_depth=1..5)`
- `graph_from_reader(reader, horse_id, max_depth=1..5)`
- `ancestor_crosses(graph)`
- `pedigree_similarity(left_graph, right_graph)`

The graph follows only `parent_relation.role=sire|dam` where `resolution_status=RESOLVED_EXACT|RESOLVED_ALIAS` and `resolved_parent_horse_id` is present. Unresolved candidate names, sire/BMS lineage labels, and fuzzy aliases **never** count as canonical ancestors. `broodmare_sire` relation is a contextual edge, **not** a third direct parent and is not traversed as a parent edge. Cycles, duplicate role rows and contradictory unresolved-ID rows are rejected or marked as unresolved.

## Semantics and caveats

- `path` uses S (sire) and D (dam), e.g. SSD for sire→sire→dam.
- A cross is the **same canonical ancestor ID** observed at >=2 distinct paths. Its paths and depths are shown; lack of observed cross does not prove a cross is absent when ancestry is incomplete.
- Similarity reports common **observed unique ancestor IDs** and a descriptive Jaccard fraction. With partial ancestry it is not directly comparable across horses and must not be ranked as a breeding/suitability prediction.
- `coverage=FULL` only when all 2+4+...+2^depth ancestor paths are resolved; otherwise `PARTIAL`. Incomplete branches do not generate imaginary descendants.
- Avoid calling a 5-generation completeness claim when only 2-generation IDs were actually resolved.
- Source uses canonical current pedigree generation `eeca93556584a5b8`. As-of historic use requires separately date-safe ancestry, not just the current profile snapshot.

## Coverage constraints

The initial 2010–2025 UKC canonical master contains 82,107 horses but only a limited subset of parents can be independently resolved by identity. The previous 2025 target audit reported: sire's sire 319; sire's dam 604; dam's sire 943; dam's dam 1,179. Those figures reflect **limited recursively resolvable IDs**, not a validated full pedigree chart.

Next: run coverage histograms for depth 2/3/4/5, unresolved status distribution, duplicate/cycle audit, and comparison of father/mother path availability. Do not assume larger depths are useful until coverage is measured.

## Ancestor source expansion gates

Before accepting external ancestor IDs:
1. Inventory any available licensed official identifiers and exact crosswalks.
2. Preserve `source_id`, `source_version`, observed/as-of date, relationship role and source URL/license.
3. Verify each ID match independently, with name collisions unresolved.
4. Keep source-native IDs distinct from JRDB horse_id until an audited canonical crosswalk exists.
5. Never fabricate unknown ancestors to fill 3–5 generations.
6. Publish immutable extended generation with manifest, audit, SHA and rollback before changing CURRENT.

## Tests

`tests/test_brdb_ancestor_graph.py` covers:
- 2-path same-ID cross
- unknown ancestor is not assumed identical
- cycle rejection
- contradictory unresolved-ID rejection
- duplicate role rejection
- maximum-depth guard
- observed similarity with partial coverage

Tests are committed but have **not yet been independently executed**. Do not mark Phase 4 complete before running tests and real generation coverage audit.

## Next acceptance

1. Execute focused new tests and entire BRDB test suite.
2. Run bounded 2025 cohort depth 2–5 against verified BRDB CURRENT Reader and record status counts.
3. Decide trusted supplementary ancestor source, if necessary, without production cutover.
4. With sufficient coverage, add explicit cross generation (e.g. 3×4) semantics and evidence audit.
5. Preserve all Blood Review v0.1 production outputs and keep PWA release independently gated.

## Depth coverage / older UKC decision (2026-10-22)

Added `src/audit_brdb_ancestor_depth_coverage.py`: it reads the verified BRDB CURRENT through `BloodReviewReader`, measures depth 2–5 for a **birth-year cohort** and emits an all-master unresolved parent birth-year / role / status frequency table. A 2025 birth cohort is **not equivalent** to the 11,818-horse cohort observed in the UKC_2025 annual archive; do not compare their denominator or claim the same coverage.

Canonical parquet reading requires DuckDB. The managed container lacks DuckDB; a normal `pip install duckdb==1.1.3` attempt failed due DNS/network transport, so this turn **did not execute** the real Parquet audit. Do not interpret the pre-existing 2025 audit's four grandparent count values as an independent depth-5 distribution. Execute the audit using the repository's `tools/data-storage/` managed-runtime / sanctioned Actions fallback and record output and test command in a RESULT before accepting any new source window.

**Decision pending evidence:** UKC files dated 2010–2025 can contain horses born before 2010, so year-of-archive is not year-of-birth. An unresolved parent's birth year older than 2010 does not by itself prove a pre-2010 UKC archive exists or that it will resolve the horse. First inventory birth-year/status frequencies and source availability; then check JRDB official/contracted historical UKC source and alternative JRDB pedigree identifiers. External sites are a last resort, require license/provenance approval, and never introduce horse-name-only identity matching.

## Maintenance-period work — independent of older UKC (2026-10-22)

The official JRDB site is temporarily unavailable. No new source archive is assumed or fetched. Existing BRDB CURRENT and frozen `brdb-review-v0.1` remain unchanged.

Added `src/brdb_ancestor_evidence.py` and `tests/test_brdb_ancestor_evidence.py`:

- `summarize_graph`: explicit generation 1..5 expected/resolved/unresolved ancestor path counts. An unenumerated branch counts as unknown, never a confirmed absence.
- `describe_crosses`: repeated **canonical ancestor horse_id** paths with generation labels, including descriptive `3×4` notation; no inbreeding coefficient, weighting, or ability claim.
- `compare_observed_ancestors`: reports shared IDs and observed Jaccard with `can_rank_similarity=false` whenever either chart is incomplete. The existing 2025 cohort has zero fully resolved depth-2..5 graphs in accepted audit #2134, so research-overlap values must not be presented as rankings.
- Fixture tests include partial graphs, explicit complete synthetic graphs, cross notation and duplicate-path rejection.

**Production gate:** This work is research-only. Do not merge it into published Newspaper/PWA, score, recommendation, or CURRENT. No external source is necessary for these contract improvements. The added tests have not been independently executed in this turn.

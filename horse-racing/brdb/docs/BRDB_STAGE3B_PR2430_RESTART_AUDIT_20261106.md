# ③-B PR #2430 restart: verified inputs and remaining transport

Status: PARTIAL / top-50 enrichment and real cohort E2E pending. Existing PR remains draft; no CURRENT or consumer change.

The previous session reported environment initialization failure `failed to query executor configuration capabilities` followed by `No usable execution environment is available. Wait for an environment to become available before using this tool.` The failure happened before command launch; neither checkout nor Python dependency failure was established. In this session the managed runtime reached running/connected, `pwd`, checkout, and data-storage `check-deps` succeeded. Python 3.12.14, DuckDB 1.1.3, PyArrow 25.0.1 were available. This identifies recovery of the execution route, not the underlying infrastructure root cause.

The approved native Drive connector supplied the existing #2223 generation ZIP. SHA-256 of its actual bytes: `672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4`. Extracted generation manifest `7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c`; actual `pedigree_fact.parquet` `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536`; actual `parent_relation.parquet` `c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85`. Values match prior manifest and instructed pins.

PR head `40741d61deeba05c412ec7752f2eeb66b9a0372d` was checked out in an isolated worktree. `python -m unittest discover -s horse-racing/brdb/tests -p 'test_brdb_stage3*.py' -v` initially executed 39 tests, zero failures. After correcting the batch-2 input contract, the same command executed 42 tests, zero failures. Existing `src/run_brdb_stage3b_crosswalk_audit.py` ran on the pinned real Parquet and its committed registry/bridge: two child identities, four source-recorded parent edges, 29 pending, zero new canonical JRDB ancestor IDs. Separately, a read-only comparison of all five v0.2 registry entries against eight JRDB profile fields found five matches, zero mismatches; it does not independently verify JBIS pages or the 50-horse graph.

The full Stage 3-A ranking CSV and the Stage 3-B 50-subject JSON have not been transported to this runtime. A separate environment reported their respective SHA-256 values `e982e7b5a1467af5bb18e74f583acd9315263a74516472ca439c88b0f2eaf362` and `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0`; those values have not been verified on files in this runtime. `/mnt/data` from that environment is absent here. The earlier audit also names a `stage3b_hybrid_2crosswalk_26paths.json` baseline required by the batch-2 runner; that file must be transferred or reproducibly rebuilt through the existing hybrid audit and verified before claiming the batch-2 E2E. The hybrid producer emits `pending`, whereas the batch-2 consumer expected `still_pending`; the PR now accepts either spelling while rejecting conflicting lists and duplicate slots. Actual input-to-input E2E is still pending.

The earlier 1st/2nd/3rd generation name totals 100/100, 147/200, 20/400 and JRDB ID totals 36/100, 10/200, 0/400 are **previously reported**, not newly recomputed. 3rd-party page research, new all-50 identity graph, updated coverage, and full Parquet E2E remain outstanding. Same-day/as-of availability is unverified. No name or lineage code is promoted to an individual ID.

Reproduction when inputs become available:

```sh
python -m unittest discover -s horse-racing/brdb/tests -p 'test_brdb_stage3*.py' -v
python horse-racing/brdb/src/run_brdb_stage3b_crosswalk_audit.py --pedigree PEDIGREE_PARQUET --crosswalk horse-racing/brdb/taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_1.json --bridge horse-racing/brdb/taxonomy/stage3b_priority4_bridge_candidate_v0_4.json --output CROSSWALK_JSON
python horse-racing/brdb/src/brdb_stage3b_top50_builder.py --pedigree PEDIGREE_PARQUET --relations RELATION_PARQUET --ranking RANKING_CSV --external-seed horse-racing/brdb/taxonomy/stage3b_external_top50_pedigrees_candidate_v0_1.json --output TOP50_BUILDER_OUTPUT_JSON
```

Do not treat TOP50_BUILDER_OUTPUT_JSON as the original research JSON: the prior report explicitly states their schemas and output hashes differ. Follow the existing batch-2 report for the original JSON and hybrid baseline. The repo branch and logs contain no private source inventory.

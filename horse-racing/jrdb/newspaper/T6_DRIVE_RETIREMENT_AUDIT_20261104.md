# EdgeDB / Training Edge retirement — T6 Drive inventory audit (2026-11-04)

Status: **INVENTORY PERFORMED / NO VERIFIED DELETE TARGET; PHYSICAL DELETION = 0**.
This is an observed inventory of the currently connected native Google Drive account, not proof of worldwide nonexistence or a claim that a prior operator deleted the assets. T7 final closure requires a separate decision concerning this scoped observation.

## Scope and rules

- Authorized task: T6 identify and remove **dedicated retired EdgeDB / legacy Training Edge Drive assets** only after confirming exact file ID, parent, identity and absence of live/repro/shared dependency.
- Preserve canonical JRDB Raw/PACI, Historical Warehouse, Index Base/record-hash utilities, Analysis Parquet, Fact Lite, Stats Mart, RaceNote, RRDB, Eval, independent Training Research, immutable revisions, frozen research evidence, all unrelated Google Drive files, GitHub Release history, and historical GitHub archive.
- Deletion tool exposed by this Drive connector is **permanent deletion**, not a trash operation. No deletion was attempted because no eligible file/folder identity was verified.

## Historical storage locator (not a current Drive readback)

Retrieved from Git history at `d8bb12199b891d37d1101591ba16fece038b9f49`:

- `horse-racing/jrdb/docs/EdgeDB_Storage_Inventory_20260925.md`
- `horse-racing/jrdb/docs/EdgeDB_Parquet_Canonical_Migration_Result_20260925.md`

The September 2026 canonical locations were:

```text
GPT/horse-racing/20_mart/edge/feature_mart/v0.2/
  current.json
  generations/edge_feature_mart_v0_2_g20260925_pq1/edge_runner_fact.parquet
GPT/horse-racing/20_mart/edge/registry/v0.2/
  current.json
  generations/edge_registry_v0_2_g20260925_pq1/
    edge_definition.parquet
    edge_metric_snapshot.parquet
    edge_registry_meta.parquet
    edge_validation_event.parquet
    edge_serving_catalog.jsonl
```

Historical Feature Mart Parquet metadata: 781,161 rows, 30,112,029 bytes, SHA-256 `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`.
These are **historical locations and identifiers only**; no current Drive file ID was supplied by those old documents.

## Connected Drive observations (2026-11-04)

- Verified current `GPT` folder: `1hO4TDAjfS5EPOx-hNFbr-1Gdmp4XaVNQ`.
- Verified `GPT/horse-racing`: `1uqorxJHB9saAgioodXuWgdJWQfgWbjiN`.
- Verified `GPT/horse-racing/20_mart`: `1ASZK3OZZh7gj0xDLOe_LLlZm9jS6tK5A`. **Direct folder listing returned six children, with no `edge` child**:
  `blood_review`, `rrdb_course_fit`, `race_review`, `racenote`, `fact_lite`, `analysis`.
- Verified `GPT/horse-racing/10_warehouse`: `1lOJwET_MUuMktVVy_1ln3mRP5wZXJBpp`, with `analysis` and `jrdb` children. These are preserved common sources, not EdgeDB deletion targets.
- Drive-wide name-filter queries `name contains 'edge'`, `'Edge'`, `'EDGE'`, `'RL'`, `'training'`, `'Training'`, `'registry'` and targeted `'edge_definition.parquet'`, `'edge_feature_mart_v0_2_g20260925_pq1'`, `'edge_registry_v0_2_g20260925_pq1'`: **zero EdgeDB-/RL-specific matching file/folder candidates**. General keyword searches for `EdgeDB`, `Training Edge` returned an unrelated RaceNote Forecast Gen0 verification spreadsheet (content match), which was retained.
- `training_research` folder `1QQjP_kE1sJ2HxkQEe2UnXOUVeqZMaHVf` exists and was retained as independent frozen research; its name does not authorize deletion.
- General `JRDB` name query resolves current historical Warehouse-related `jrdb` folder(s), not a verified old `GPT/JRDB` root. Do not delete a matching warehouse folder by name alone.
- Zero candidates may also mean assets were previously removed, moved elsewhere, unavailable to this Drive connection, or inaccessible to the current search. No claim is made about their disposition.

## T6 action log and acceptance

| Gate | Result |
|---|---|
| Historical Edge-only storage targets identified | PASS (paths/generations, not current file IDs) |
| Current canonical folder listed directly | PASS |
| Cross-check of exact generation names and broad name searches | PASS in connected Drive scope |
| Exact live Edge-only Drive file IDs ready for safe deletion | **0 verified** |
| Drive files permanently deleted | **0** |
| Independent current files/immutable research preserved | PASS (no Drive writes attempted) |
| Proof historical Edge-only assets are fully absent from all locations/connections | **NOT ESTABLISHED** |

**Operational conclusion:** T6 inventory is complete for currently visible connected Drive locations, but no physical cleanup took place. Mark `T6_DELETE_EXECUTED = NO`; mark `T6_VERIFIED_TARGETS = 0`. Never record this as “deleted” or as a verified global absence. If an Edge-only folder/file resurfaces in another accessible account/legacy root, repeat exact metadata, dependency and ownership checks before a targeted deletion. The preceding T5 PACI-only Current and Pages publish is unaffected.

## Follow-up: user-completed cleanup (2026-11-04)

After the connected-Drive inventory above, the user clarified that the old assets had been **moved to a separate holding location** and explicitly reported: 「退避していたのを忘れてました。私が削除しておきました。」 (the user had forgotten the assets were held elsewhere and has deleted them personally).

Classification:
- **User-attested deletion of relocated retirement assets: DONE (reported).** This explains why they were not found under the previously recorded canonical Drive folder.
- **Deletion by the assistant/Google Drive connector: 0 files.** No delete request or Drive write was made by the assistant during T6.
- **Independent verification of the holding location, exact file IDs, complete deletion coverage and trash/permanent-delete status: NOT PERFORMED / UNKNOWN.** No deleted-file inventory or metadata was supplied.
- **T6 status:** `INVENTORY_COMPLETE; RELOCATED_ASSET_CLEANUP_USER_REPORTED_DONE`. Do not treat the earlier zero-candidate observation as proof of global absence; do not retroactively claim tool-verified deletion.
- **T7 implication:** The reported asset cleanup resolves the known intended manual-cleanup action on a user-attestation basis. A final retirement conclusion should distinguish this from independently audited Drive deletion and keep other projects' independent research/frozen files out of scope.

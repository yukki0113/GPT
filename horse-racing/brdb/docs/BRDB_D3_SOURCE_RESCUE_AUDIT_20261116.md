# BRDB D3 fixed-source recovery and exact replay audit — 2026-11-16/17

Status: **PASS — FIXED INPUTS RECOVERED / CANONICAL DUCKDB REPLAY EXACT / LIBRARY READBACK VERIFIED**.

This is a research-only recovery audit. It does not authorize prediction integration, BRDB CURRENT mutation, RaceNote/PWA/Newspaper publication, or any score/rank production.

## 1. Fixed inputs recovered

- JRDB Analysis v1.4 generation: `analysis-v1_4-postrace-20261101-01`.
- Original Drive `manifest.json`: recovered.
- Historical fact partitions: **11/11 (2016–2026)** recovered through the established Drive → Data Storage route; every size and SHA-256 matched the immutable manifest.
- Stage3-B top50 source recovered from `brdb_stage3b_top50_batch_audit_v2_20261106.zip`.
- top50 SHA-256: `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0`.
- Canonical D3 runner SHA-256: `b6a45321b1fb9016bc08dc75564557ea9ade01e033231616315f94a6893bc7b4`.

## 2. Project routing correction

The interim statement that a local DuckDB install failure or a newly introduced license gate blocked this Project was incorrect.

The authoritative route is the existing Project contract:
- `PROJECT_SOURCES_GUIDE_261102.md`: normal Drive sharing model and `tools/data-storage/` fallback are established Project operation.
- `tools/data-storage/README.md` / `docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`: local dependency failure -> one repair attempt -> `[DATA_STORAGE_FALLBACK]` Actions route.
- `docs/DYNAMIC_DRIVE_MANIFEST_RUNBOOK.md`: real JRDB Drive -> Actions -> DuckDB E2E previously accepted; existing folder-wide sharing policy remains unchanged.

No new permission model or external-policy gate is introduced here.

## 3. Replay tooling added

- `config/public_drive/d3_fixed_replay_20261101_v0_1.json`: exact Drive IDs, expected names, sizes and SHA-256 for the fixed D3 replay inputs.
- `src/verify_brdb_d3_restoration.py`: fail-closed two-run verifier. It requires the fixed generation, 11 partitions, top50 SHA and canonical runner SHA, runs the unchanged D3 DuckDB entrypoint twice, and accepts only the three frozen output SHA values.
- `src/run_brdb_d3_fixed_fallback.py`: Data Storage fallback wrapper that restores the historical Analysis layout and exact 161-byte `current.json` format, extracts only the fixed top50 JSON from the accepted Stage3-B archive, then calls the verifier.
- `tests/test_verify_brdb_d3_restoration.py`: offline guard tests.

## 4. Failure diagnosis and correction

Three fail-closed attempts were retained as audit evidence:
1. Run `44022626711`: Drive inputs all SHA-verified; failed because reconstructed Analysis layout omitted `generations/<generation>/manifest.json`.
2. Run `44022910318`: canonical D3 computation completed but frozen output SHA differed.
3. Run `44023179134`: diagnostic hashes showed `d3_temporal_diagnostic.json` already matched exactly, while full/receipt differed. Root cause was the reconstructed `current.json` key order; D3 full evidence records `source_sha256.current_pointer`.

Drive revision history showed the accepted 2026-11-02 pointer revision was **161 bytes**, same format family as adjacent 2026-10-26 and 2026-11-08 revisions. Restoring the historical key order `status -> generation_id -> manifest` reproduced the accepted pointer bytes.

## 5. Canonical PASS

Owner-created request: [#2616](https://github.com/yukki0113/GPT/issues/2616)  
Actions run: [44023639295](https://github.com/yukki0113/GPT/actions/runs/44023639295)  
Artifact: `data-storage-fallback-44023639295` (ID `14302451395`)  
Source commit: `f9af10745b8c7be9caf71009a46d0cb40694f9cc`  
DuckDB: **1.1.3**  
PyArrow: **25.0.1**  
Fallback status: **PASS**  
Canonical replay step: exit code **0**, elapsed **11.713234s**.

The verifier ran the unchanged D3 generator **twice** and reported:
- `two_run_byte_identity=true`
- `research_only=true`
- `prediction_safe=false`
- `historical_asof_status=AS_OF_UNVERIFIED`

Exact restored output SHA-256:

| output | SHA-256 |
|---|---|
| `d3_full_condition_evidence.json` | `705a85d4c43b369b14cbba9177f5af13ed3111f1a5031a97ee76acf51064e764` |
| `d3_temporal_diagnostic.json` | `27abb3aafabd8b5350009cf8623d43246bda70365427cc772d07e3aba4d8c8bf` |
| `d3_run_receipt.json` | `4a128dc02baf4a6ee82a1b560fa1cafb62f540cba8bed38511a97af43c3abd2e` |

These are **exactly the previously accepted D3 pins**. No pin was changed to fit new output.

## 6. Durable Library storage and independent readback

Stored under ChatGPT Library:
- `/BRDB/D3/d3_full_condition_evidence.json`
- `/BRDB/D3/d3_temporal_diagnostic.json`
- `/BRDB/D3/d3_run_receipt.json`
- `/BRDB/D3/restoration_receipt_20261117.json`

Each file was materialized back from Library after upload. Independent SHA-256 readback matched the values above. Restoration receipt SHA-256:
`b1097d1f8a861d150f1a2899f27385c7e4d009b3e9a176699fce9b183268d70d`.

The earlier source recovery ZIP remains at:
`/BRDB/BRDB_D3_FIXED_INPUTS_RECOVERY_20261116.zip`.

## 7. Boundary

D3 recovery is now **complete as an exact research replay**. This does not alter the original D3 scientific boundary: retrospective descriptive evidence, `AS_OF_UNVERIFIED`, not causal and not prediction-safe.

The D4 real-PACI E2E gate may now consume the restored three exact D3 files. Keep PR #2603 draft until the D4 full-field acceptance gate itself passes.

# BRDB D3 fixed-source rescue audit — 2026-11-16

Status: **ALL FIXED INPUTS RECOVERED AND VERIFIED / ACTIONS FALLBACK ROUTING NOT YET COMPLETE**. A local DuckDB package restriction is *not* a project-level execution blocker.

## Recovered canonical inputs

- JRDB Analysis v1.4 generation: `analysis-v1_4-postrace-20261101-01`.
- Original Drive `manifest.json` from that exact generation: all **11 annual fact partitions (2016–2026)** recovered from the connected canonical storage folders, and **every file's size and SHA-256** matched the exact immutable manifest.
- Original Stage3-B top50 `stage3b_top50_master_research.json` recovered as `input_top50.json` from the previously accepted private `brdb_stage3b_top50_batch_audit_v2_20261106.zip`; **SHA-256 verified**: `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0`.
- Source code (`brdb_d3_condition_research.py`, `brdb_d3_temporal_validation.py`, `run_brdb_d3_research_e2e.py`) recovered from existing GitHub Actions run [43830804006](https://github.com/yukki0113/GPT/actions/runs/43830804006), artifact `14207809833`; all three files' **Git blob SHA matched main**.
- The local `analysis/current.json` is **a reconstructed pointer**, not the original Drive `current.json`; exact original `manifest.json` and original Parquet bytes are preserved. The D3 Reader uses the pointer to identify the accepted generation and manifest path.

## Durable private recovery artifact

- ChatGPT Library path: `/BRDB/BRDB_D3_FIXED_INPUTS_RECOVERY_20261116.zip`
- Size: **12,456,465 bytes**; ZIP entries: **19**.
- Archive SHA-256: `13ddbe1f6e0b3db5b832ffb14000d2891c18222f911dcb87a63b9d05c6c65054`.
- **Library upload and materialized readback:** byte-for-byte SHA-256 match; ZIP CRC `testzip()` returned no error.
- Archive contains the original licensed fixed Parquet inputs, original top50 master, original GitHub sources, manifest, source receipts, reproduction instructions; **DO NOT publish its contents in GitHub**. Only the private Library has the licensed payload.

## Mandatory data-storage fallback (do not stop at local dependency failure)

The execution environment lacked `duckdb`; a single normal dependency-install attempt (`duckdb==1.1.3`) failed under the restricted package index/network. The canonical D3 implementation depends on DuckDB SQL. It must **not** be silently rewritten using pandas/PyArrow or otherwise altered solely to bypass environment constraints.

The repository's authoritative route is `tools/data-storage/README.md` -> `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md` -> `[DATA_STORAGE_FALLBACK]` issue -> `.github/workflows/data_storage_fallback_issue.yml`, after determining whether the private-input transfer meets licensing and the approved transport contract. The prior report incorrectly stopped at local install failure without resolving this fallback route.

**Transport eligibility preflight, 2026-11-16:**
- The 2016 Parquet Drive file and Stage3B audit ZIP were observed with `anyone:reader` metadata. This alone **does not prove that the JRDB data license permits anonymous Actions downloads**.
- The reviewed public-drive manifest, if created, must contain exact file IDs, expected names, sizes and SHA-256 and must be approved for this source. Avoid publishing private licensed assets or creating newly public permissions.
- If licensed public fetching is permitted: use `public_drive_inputs` or the documented dynamic registry route, and retain canonical DuckDB execution in Actions.
- If authenticated/private transport is required: the optional encrypted bridge is documented in `tools/data-storage/docs/DRIVE_GPT_ACTIONS_BRIDGE.md`, but its own runbook states the requisite RSA Actions secret was **not configured**, and the bridge requires an additional authorized scoped GH_TOKEN; do not imply it is already runnable.
- No GitHub Actions run was initiated for D3 reconstruction during this task because no approved transport for these **licensed fixed inputs** had been established.

**No new D3 output JSON was produced in this turn.** Prior documented expected SHA-256 remain the acceptance pins:
- `d3_full_condition_evidence.json`: `705a85d4c43b369b14cbba9177f5af13ed3111f1a5031a97ee76acf51064e764`
- `d3_temporal_diagnostic.json`: `27abb3aafabd8b5350009cf8623d43246bda70365427cc772d07e3aba4d8c8bf`
- `d3_run_receipt.json`: `4a128dc02baf4a6ee82a1b560fa1cafb62f540cba8bed38511a97af43c3abd2e`

Run on a permitted DuckDB-equipped private environment with the exact archived bytes, using:
```bash
python src/run_brdb_d3_research_e2e.py \
 --analysis-root analysis \
 --top50 stage3b_top50_master_research.json \
 --output-dir output
```
Check generated SHA against all **three** pins **before** accepting D3 reconstruction or D4 real PACI E2E. Do not update those pins to match new output.

## Operational safeguards
- BRDB CURRENT, RaceNote, PWA, Newspaper, frozen Blood Review contracts, source repo modules and data generation were not changed.
- Research-only: `AS_OF_UNVERIFIED` / `prediction_safe=false`. The original D3 outcomes are retrospective and are not pre-off-time feature evidence.
- This is a source-recovery progress checkpoint, not a proof that new D3 E2E passed. Keep [D4 PR #2603](https://github.com/yukki0113/GPT/pull/2603) as draft until end-to-end acceptance.

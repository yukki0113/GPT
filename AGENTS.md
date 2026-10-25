# Repository Agent Instructions

Applies to all work in this repository. Read the relevant project README / CONTEXT / WORKFLOW as well; these instructions do not replace project-specific rules.

## Mandatory Parquet / DuckDB routing

**Before inspecting, reading, writing, converting, querying, validating, benchmarking, or transporting Parquet datasets, or changing DuckDB-related code, first read `tools/data-storage/README.md`.** This includes tasks whose primary objective is forecasting, testing, PWA updates, or data acquisition when their execution uses Parquet / DuckDB. Follow its linked operational contracts before choosing an implementation or concluding that execution is blocked.

1. Discover and reuse existing `tools/data-storage/` CLI, config-driven execution, scripts and project configs before writing project-local equivalents. Prefer existing project-specific validated entrypoints where the common tool delegates domain logic to them.
2. Distinguish **input acquisition** from **query execution**. Reuse the registered Drive routes in `tools/data-storage/config/drive_source_registry.json` and `tools/data-storage/docs/DYNAMIC_DRIVE_MANIFEST_RUNBOOK.md` where applicable, as well as the existing static/artifact/private-input routes documented in the README. Do not invent file IDs, hashes, connector paths, or Drive permissions.
3. For local execution, run the documented `data_storage check-deps` preflight and, if needed, the documented pinned-requirements repair **once**. Reuse a healthy environment instead of reinstalling dependencies repeatedly.
4. When local repair is blocked by a managed runtime's network/proxy policy, evaluate the existing `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md` and `.github/workflows/data_storage_fallback_issue.yml`. If eligible, use the canonical Actions route; inspect its audit and output artifact before claiming success. Where private inputs or domain-specific safeguards preclude generic fallback, use only an already approved project workflow/transport.
5. Do not silently change DuckDB SQL to a different engine, change data or scientific semantics, relax validations, place restricted datasets in public issues/artifacts, or introduce an unreviewed competing data-storage implementation to work around runtime restrictions.
6. If neither local nor approved fallback execution is feasible, report **which preflight failed**, **which existing fallback paths were examined**, **why each was inapplicable**, and the **specific missing prerequisite**. Missing `duckdb` alone is not a terminal diagnosis.
7. In the final work report for an affected task, state the canonical tool/entrypoint used, input route, execution route (local / Actions / blocked), and verification evidence (audit, test, or run URL, if available). Do not claim tests or execution that did not run.

### Scope and exceptions

- Parquet is the analytical file format; DuckDB is the query engine. Transactional or point-update workloads may appropriately continue to use SQLite, as the common README explains.
- This rule does **not** require introducing Parquet or DuckDB into unrelated tasks, or replacing established project logic merely for consistency.
- If an existing path cannot satisfy a genuine requirement, explain the gap and propose a reviewed extension to the shared package before creating a local duplicate.
- Repository and runtime permissions still apply. These instructions do not authorize data publication, credential exposure, permission changes, or unreviewed GitHub Actions execution.

Canonical source of detail: [tools/data-storage/README.md](tools/data-storage/README.md). Do not copy the detailed bootstrap, Drive transport or fallback implementations into this file; follow the current canonical documentation.

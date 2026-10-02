# RL Retirement T3 — Downstream Non-Dependency Audit

Date: 2026-10-02
Contract: `RL_Retirement_Contract_20261002.md`

## 1. Result

RL / Training Edge outputが存在しなくても、現行のNewspaper / RaceNote / EdgeDB / PWAが通常運用できることを静的監査で確認した。

```text
RACENOTE_RL_REQUIRED               = FALSE
NEWSPAPER_RL_REQUIRED              = FALSE
EDGEDB_RL_REQUIRED                 = FALSE
PWA_RL_REQUIRED                    = FALSE

ACTIVE_MY_INDEX_ARGUMENT_COUNT     = 0
RL_ABSENCE_FAILURE_PATH_COUNT      = 0

T3_DOWNSTREAM_NONDEPENDENCY        = PASS
```

## 2. Formal audit evidence

Issue:

```text
#1720
[JRDB_RL_RETIREMENT_T3_AUDIT] downstream-nondependency-20261002
```

Run:

```text
36949876100
head_sha = f2647561e9cc28676b7c571af27c6aa8abc27018
conclusion = success
```

Artifact:

```text
id     = 11203452444
name   = jrdb-rl-retirement-t3-36949876100
digest = sha256:490ac80a553891c0eb0137a264d92bcf1af595ab654a0369b3c07e757bde28d5
```

Audit result:

```text
status        = PASS
failure_count = 0
active workflows scanned = 138
```

## 3. Active workflow audit

The audit searched all active files under `.github/workflows/` for normal-production references to:

- `--my-index-csv`
- `score_training_edge_v0_2_daily.py`
- `project_training_edge_v0_2_input.py`
- `training_edge_v0_2_core.py`
- `build_jrdb_training_research.py`
- `migrate_jrdb_training_research_parquet.py`

Result:

```text
active_workflows_do_not_require_rl = PASS
hit_count                           = 0
```

Therefore no active workflow requires RL / Training Edge generation to satisfy a downstream job.

## 4. Newspaper compatibility

`jrdb_newspaper_merge_external.py` retains historical `my_index` / `training_edge_index` support only for backward compatibility.

The following are now explicit:

- `my_index_csv: Path | None = None`
- the no-input path is supported
- the CLI help marks `--my-index-csv` as retired compatibility input
- normal production must omit it
- normal production must not generate RL on demand

No active workflow passes `--my-index-csv`.

The base Newspaper schema may retain `addons.my_index = null` for compatibility. A null or absent RL value is normal.

## 5. RaceNote firewall

RaceNote already contained anti-RL boundaries and they were intentionally preserved.

Verified:

```text
racenote_general_training_edge_hidden              = PASS
racenote_general_rl_index_hidden                    = PASS
racenote_synthesis_rejects_training_edge_visibility = PASS
racenote_synthesis_do_not_use_training_edge         = PASS
racenote_forecast_training_edge_hidden              = PASS
racenote_card_training_edge_not_consumed            = PASS
```

The relevant current contract remains:

```text
training_edge_visible = false
rl_index_visible      = false
do_not_use_training_edge = true
training_edge_status  = NOT_CONSUMED
```

These checks are retained as anti-dependency firewalls after RL retirement.

## 6. EdgeDB / PWA

Active EdgeDB and PWA source/workflow paths were scanned for hard references to retired RL inputs.

Forbidden dependency patterns included:

- `--my-index-csv`
- `training_edge_index`
- retired Training Edge scorer/projector
- `rl_index`
- RaceLift / RL-T input references

Result:

```text
edgedb_pwa_no_rl_hard_dependency = PASS
hit_count                         = 0
```

EdgeDB and PWA remain independent production systems.

## 7. Code change

`horse-racing/jrdb/src/jrdb_newspaper_merge_external.py`

was updated so the historical Training Edge merge path is explicitly documented as:

```text
Historical compatibility only
RL / Training Edge production generation is retired
Normal Newspaper production must not require or auto-create this input
```

No Newspaper schema or value interpretation was changed.

## 8. Audit implementation

Permanent audit script:

`horse-racing/jrdb/src/audit_rl_retirement_downstream_dependencies.py`

This script is retained for T6 final retirement verification.

The temporary T3 Actions entrypoint was removed after the successful run:

`.github/workflows/jrdb_rl_retirement_t3_audit_issue.yml`

Therefore T3 does not leave a new active RL workflow behind.

## 9. Gate

```text
RACENOTE_RL_REQUIRED               = FALSE
NEWSPAPER_RL_REQUIRED              = FALSE
EDGEDB_RL_REQUIRED                 = FALSE
PWA_RL_REQUIRED                    = FALSE

ACTIVE_MY_INDEX_ARGUMENT_COUNT     = 0
RL_ABSENCE_FAILURE_PATH_COUNT      = 0

T3_DOWNSTREAM_NONDEPENDENCY        = PASS
```

Next cleanup stage: T4 — frozen RL research asset inventory / freeze.

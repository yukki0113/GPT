# JRDB Result Query GPT Runtime Runbook v0.1

## Purpose

This runbook is the canonical GPT / Work procedure for executing
`src/jrdb_result_query.py` against JRDB SED + HJC when a chat runtime does
not have the repository or Raw files pre-mounted.

The goal is to make completed-race result lookup reproducible across threads:

```text
GitHub main source
  + native Google Drive SED/HJC
  -> GPT runtime
  -> jrdb_result_query_runner.py
  -> deterministic result JSON
```

Do not reimplement fixed-width parsing in a chat, notebook, or one-off script.
Do not treat "the Raw ZIP is not in Git" as a reason to use the Web.

## Authorities

- repository: `yukki0113/GPT`
- branch: latest `main`
- project root: `horse-racing/jrdb/`
- operational entrypoint: `src/jrdb_result_query_runner.py`
- query engine: `src/jrdb_result_query.py`
- fixed-width authority: `src/jrdb_raw.py`
- transitive import required by `jrdb_raw.py`: `src/jrdb_ukc.py`
- result contract: `docs/README_jrdb_result_query.md`

For current Raw mode, Python 3.10+ and the standard library are sufficient.
Do not install DuckDB for a normal 2026+ SED/HJC query. DuckDB is needed only
for the historical Warehouse mode documented separately.

## Mandatory execution rule for a new thread

A new Chat / Work thread must not assume that repository source exists under
`/mnt/data`. First inspect the runtime.

There are two valid source states:

1. **Repository checkout already exists**: execute the latest `main` files
   directly from `horse-racing/jrdb/src/`.
2. **No checkout exists**: materialize the exact source bundle from GitHub
   `main` into the runtime before executing.

Never reconstruct these modules from memory or copy parser logic into a new
notebook.

## Step 1 — Materialize the source bundle

When there is no local checkout, fetch these four UTF-8 files from GitHub
`main` with the GitHub connector:

```text
horse-racing/jrdb/src/jrdb_result_query_runner.py
horse-racing/jrdb/src/jrdb_result_query.py
horse-racing/jrdb/src/jrdb_raw.py
horse-racing/jrdb/src/jrdb_ukc.py
```

Write the returned file contents unchanged to:

```text
/mnt/data/jrdb_result_query_runtime/src/
  jrdb_result_query_runner.py
  jrdb_result_query.py
  jrdb_raw.py
  jrdb_ukc.py
```

All four files must come from the same current `main` observation. Do not mix
a cached runner with newer parser modules.

If a repository checkout is available, this materialization step may be
skipped and `SRC` may point to the checkout's
`horse-racing/jrdb/src` directory.

### Source preflight

Before touching result Raw, run:

```bash
SRC=/mnt/data/jrdb_result_query_runtime/src

python -m py_compile \
  "$SRC/jrdb_result_query_runner.py" \
  "$SRC/jrdb_result_query.py" \
  "$SRC/jrdb_raw.py" \
  "$SRC/jrdb_ukc.py"

python "$SRC/jrdb_result_query_runner.py" --version
```

Expected runner version for the current v0.1 contract:

```text
0.1.0
```

A `ModuleNotFoundError` at this stage is a source-materialization failure.
Do not work around it by writing a substitute parser.

## Step 2 — Generate the exact Raw materialization plan

Example for 2026-10-04:

```bash
SRC=/mnt/data/jrdb_result_query_runtime/src

python "$SRC/jrdb_result_query_runner.py" \
  --date 2026-10-04 \
  --plan \
  --pretty
```

For 2026+, the plan requests daily archives:

```text
/Google Drive/GPT/horse-racing/00_raw/SED/SED261004.zip
/Google Drive/GPT/horse-racing/00_raw/HJC/HJC261004.zip
```

with local destinations:

```text
/mnt/data/jrdb_result_query/20261004/SED261004.zip
/mnt/data/jrdb_result_query/20261004/HJC261004.zip
```

For dates through 2025, the runner requests annual archives instead:

```text
SED_YYYY.zip
HJC_YYYY.zip
```

Do not guess archive names when the runner can emit them.

## Step 3 — Materialize SED and HJC from native Google Drive

Use the connected native Google Drive connector.

1. Search the canonical Drive inventory for the exact basenames emitted by
   the plan.
2. Download/materialize the exact SED and HJC ZIPs.
3. Place them at the exact `local_path` values emitted by the plan.
4. Do not rename a different date's file to satisfy the runner.
5. Do not use `gdown`, a Drive API bridge, or GitHub Actions for this
   transport.

For a current date, both are required for a complete result:

- SED: horse-level result authority, including finish and SED win/place
  cross-validation fields.
- HJC: race-level authority for all eight payout types.

SED alone is not a complete all-payout result.

If SED or HJC is genuinely absent from canonical Drive, report that the JRDB
result is not yet materialized. Do not silently switch to Web unless the user
explicitly requests a Web fallback or the calling workflow defines one.

## Step 4 — Raw ZIP preflight

Before executing the query, verify that both local files exist and are readable
ZIPs.

Example:

```bash
python - <<'PY'
from pathlib import Path
import zipfile

root = Path("/mnt/data/jrdb_result_query/20261004")
expected = {
    "SED": root / "SED261004.zip",
    "HJC": root / "HJC261004.zip",
}

for family, path in expected.items():
    if not path.is_file():
        raise SystemExit(f"missing {family}: {path}")
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad:
            raise SystemExit(f"bad ZIP member in {path}: {bad}")
        names = [Path(x).name for x in zf.namelist()]
        wanted = f"{family}261004.txt"
        if wanted not in names:
            raise SystemExit(f"{wanted} not found in {path}: {names}")

print("JRDB result Raw preflight PASS")
PY
```

Change the date token for the requested day. For annual archives, the target
daily member still must exist inside the annual ZIP.

## Step 5 — Execute through the operational runner

### Whole day

```bash
SRC=/mnt/data/jrdb_result_query_runtime/src

python "$SRC/jrdb_result_query_runner.py" \
  --date 2026-10-04 \
  --pretty \
  --output /mnt/data/20261004_JRDB_Result_Query.json
```

### One venue

```bash
python "$SRC/jrdb_result_query_runner.py" \
  --date 2026-10-04 \
  --venue 東京 \
  --pretty
```

### One race

```bash
python "$SRC/jrdb_result_query_runner.py" \
  --date 2026-10-04 \
  --venue 東京 \
  --race 10 \
  --pretty
```

### Selected payout types

```bash
python "$SRC/jrdb_result_query_runner.py" \
  --date 2026-10-04 \
  --venue 東京 \
  --race 10 \
  --bet-type 馬連 \
  --bet-type 3連複 \
  --pretty
```

The runner supplies explicit SED/HJC paths to
`jrdb_result_query.query_results()`. Do not bypass it with guessed
`--raw-root` paths in normal GPT operation.

## Step 6 — Success criteria

A complete normal result must satisfy all of the following:

- process exit code = 0
- top-level `schema_version = "jrdb-result-query-v0.1"`
- top-level `status = "success"`
- provenance says `web_used = false`
- SED and HJC are both represented in source provenance
- every returned race has `top3`
- payout groups follow the HJC contract
- SED/HJC win/place cross-validation is not mismatched

Do not hard-code a 24-race success condition. The number of races depends on
the requested date and filters.

The default result contains all eight payout families:

```text
win
place
frame_quinella
quinella
wide
exacta
trio
trifecta
```

## Known-good reference

The GPT runtime path has been proven with 2026-10-04 Raw:

```text
SED261004.zip
HJC261004.zip
```

The observed Raw contained 362 SED rows and 24 HJC race rows. SED win/place
cross-validation against HJC had no mismatch, and the day returned 24 races.

Use this as an operational reference, not as a fixture to substitute for other
dates.

## Failure matrix

| Symptom | Meaning | Required action |
| --- | --- | --- |
| `No such file ... jrdb_result_query_runner.py` | Git source was never materialized | fetch latest main source bundle first |
| `ModuleNotFoundError: jrdb_result_query` | runner and engine are not in the same importable source directory | materialize the bundle unchanged into one `src` directory |
| `ModuleNotFoundError: jrdb_raw` | incomplete source bundle | fetch `jrdb_raw.py` from the same main observation |
| `ModuleNotFoundError: jrdb_ukc` | transitive dependency omitted | fetch `jrdb_ukc.py`; do not remove the import ad hoc |
| `required Drive Raw has not been materialized` | SED/HJC local cache missing | execute the plan and materialize both ZIPs |
| `missing SED archive` / `missing HJC archive` | wrong path, wrong date, or Drive file not yet available | inspect exact plan and Drive inventory |
| bad ZIP / missing daily member | corrupted or wrong archive | reacquire the exact canonical Drive file |
| `status=partial` | one required authority is unavailable | do not present as a complete result |
| `status=review_required` | SED/HJC cross-validation mismatch | stop and audit; do not settle automatically |
| raw Python cannot reach a public site | irrelevant to JRDB Raw execution | do not replace JRDB execution with Web because of sandbox networking |

## What not to do

Do not:

- invent a second fixed-width parser in a notebook;
- manually slice SED/HJC bytes outside `jrdb_raw.py`;
- use result-page Web scraping before checking canonical JRDB Raw;
- assume GitHub files automatically exist in `/mnt/data`;
- assume Drive files automatically exist in the runtime;
- install unrelated packages to solve a missing-source-path problem;
- mix source files from different commits;
- treat SED-only output as complete all-payout data;
- use same-day/Web result data as prediction-time input.

## Minimal instruction for another thread

When handing this task to another Chat / Work thread, the instruction may be:

> Follow `horse-racing/jrdb/docs/JRDB_RESULT_QUERY_GPT_RUNTIME_RUNBOOK_v0_1.md`
> from latest GitHub main. Materialize the source bundle first, then execute the
> runner plan, materialize SED/HJC from canonical Drive to the exact planned
> paths, run the query, and accept only `status=success`. Do not create a
> substitute parser and do not use Web merely because Raw is not mounted.

That instruction is intentionally enough to bootstrap a fresh runtime without
relying on conversation memory.

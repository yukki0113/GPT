# JRDB Result Query v0.1

## Purpose

`src/jrdb_result_query.py` is the standard deterministic lookup for completed JRA race results and payouts inside the JRDB project.

Use it before general Web search when a request needs JRDB-covered:

- 1st-3rd finishers
- horse number / horse name / final win popularity / final win odds
- all payout types
- race/day/venue result lookup
- source data for hit-rate / in-the-money-rate / ROI settlement

The query tool does **not** calculate ROI itself and does **not** make predictions.

## Authorities

- SED = horse-level completed result authority
- HJC = race-level payout authority
- Common fixed-width interpretation = `src/jrdb_raw.py`

HJC supports eight payout types:

| Japanese | machine value |
| --- | --- |
| 単勝 | `win` |
| 複勝 | `place` |
| 枠連 | `frame_quinella` |
| 馬連 | `quinella` |
| ワイド | `wide` |
| 馬単 | `exacta` |
| 3連複 | `trio` |
| 3連単 | `trifecta` |

SED win/place payouts are used only as a cross-validation lane against HJC. HJC remains payout authority.

## Default response

A one-race query returns:

- race identity
- all horses whose confirmed finish is 1, 2 or 3 under `top3`
- all eight HJC payout groups
- SED/HJC availability
- win/place cross-validation
- provenance with `web_used=false`

Dead-heats are not collapsed: every horse whose confirmed finish is 1-3 is returned.

All runners are opt-in with `--include-all-runners`.

## CLI

### One day / all races

```bash
python src/jrdb_result_query.py \
  --date 2026-09-06 \
  --raw-root /path/to/00_raw \
  --pretty
```

### One venue

```bash
python src/jrdb_result_query.py \
  --date 2026-09-06 \
  --venue 阪神 \
  --raw-root /path/to/00_raw \
  --pretty
```

### One race

```bash
python src/jrdb_result_query.py \
  --date 2026-09-06 \
  --venue 阪神 \
  --race 10 \
  --raw-root /path/to/00_raw \
  --pretty
```

### One or more bet types

```bash
python src/jrdb_result_query.py \
  --date 2026-09-06 \
  --venue 阪神 \
  --race 10 \
  --bet-type ワイド \
  --bet-type 3連複 \
  --raw-root /path/to/00_raw \
  --pretty
```

Japanese aliases and canonical machine names are both accepted.

## Source modes

### Current / Raw

For normal 2026+ completed-race operation, use SED + HJC Raw.

`--raw-root` resolves these layouts:

```text
RAW_ROOT/
  SED/
    SEDyymmdd.zip
    SED_YYYY.zip
  HJC/
    HJCyymmdd.zip
    HJC_YYYY.zip
```

Explicit `--sed` and `--hjc` ZIPs are also supported.

### Historical Warehouse

Accepted 2010-2025 historical lookup can read normalized Warehouse Parquet:

```bash
python src/jrdb_result_query.py \
  --date 2024-09-29 \
  --venue 中山 \
  --race 1 \
  --source warehouse \
  --warehouse-root /materialized/jrdb/v1 \
  --warehouse-manifest /materialized/jrdb/v1/<generation>/manifest.json \
  --pretty
```

The Warehouse must provide `sed` and `hjc_payout` assets for the target year. DuckDB is required for this mode.

`--source auto` uses Warehouse for <=2025 only when both Warehouse arguments are supplied; otherwise it uses Raw. The tool itself does not call Google Drive or the Web.

## Payout representation

Each payout row exposes:

```json
{
  "numbers": [4, 12],
  "combination_text": "4-12",
  "payout_yen": 1420,
  "ordered": false,
  "number_kind": "horse"
}
```

- unordered: 枠連 / 馬連 / ワイド / 3連複
- ordered: 馬単 / 3連単
- `frame_quinella` uses `number_kind=frame`; all others use horse numbers
- blank/zero fixed-capacity HJC slots are omitted by default
- `--include-empty-slots` is audit-only

The query layer does not sort ordered combinations and does not infer refunds or special payouts from zero values.

## Result status

- `success`: SED and HJC available, cross-validation has no mismatch
- `partial`: at least one required source is unavailable
- `review_required`: SED/HJC win/place cross-validation mismatch
- `error`: invalid request or unreadable source

CLI exit codes:

- 0 success
- 2 error
- 3 partial
- 4 review_required

A missing HJC does not trigger Web fallback inside this tool.

## GPT routing rule

For JRDB-covered historical/current completed JRA races, the standard lookup order is:

```text
1. jrdb_result_query.py
2. direct JRDB Raw / Warehouse audit if needed
3. external Web only when JRDB coverage is absent or the requested fact is outside this contract
```

This rule exists to avoid repeatedly searching public result pages for facts already held in the project.

## Library API

```python
from jrdb_result_query import query_results

result = query_results(
    date="2026-09-06",
    venue="阪神",
    race_no=10,
    raw_root=Path("/path/to/00_raw"),
)
```

The returned value is the same JSON-compatible dictionary used by the CLI.

## Boundaries

- no prediction logic
- no ROI / ticket settlement logic
- no name-based joins
- no independent fixed-width offsets
- no automatic Web fallback
- no inference of refund/special-payout semantics

A future `jrdb_bet_settlement.py` can consume this stable result contract for deterministic investment/return/ROI calculations.

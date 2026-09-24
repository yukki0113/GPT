# keibailuka Historical Ledger Contract v0.1

## Canonical ledger

Google Sheets: `keibailuka Historical 検証台帳`

- Spreadsheet ID: `1bAN-nlwEBcg3qtr7SyhPkluRqiTBY2sDU2QkSbRB2jM`
- Tabs: `README`, `イルカ明細`, `取込管理`, `ダッシュボード`
- Initial research window: `2024-01` onward. `2023-01` onward can be added without code changes if more samples are needed.

The spreadsheet is the canonical accepted Historical ledger. GitHub Actions artifacts are temporary transfer/audit material, not the final data store.

## Detail key

`イルカ明細` has one row per publicly exposed keibailuka selection.

Canonical key:

```text
日付 + 会場 + R
```

A race contributes at most one free/public selection. `該当無し` and paid-lead sections are not rows.

Columns:

1. `key`: `YYYY-MM-DD|会場|nR`
2. `日付`
3. `会場`
4. `R`
5. `馬名_raw`: exact extracted horse name; masked selection remains `🤡`
6. `馬名_resolved`: only populated after the actual masked horse is independently confirmed
7. `コメント`: normalized public comment from the blog
8. `masked_flag`: `1` when `馬名_raw == 🤡`, else `0`
9. `source_url`
10. `source_method`
11. `source_month`
12. `source_run_id`
13. `imported_at`

Never overwrite `馬名_raw` when resolving a masked horse. Research joins use `馬名_resolved` when populated, otherwise `馬名_raw`.

## Import control

`取込管理` keeps one accepted row per source month.

Columns:

- `source_month`
- `status`
- `row_count`
- `day_count`
- `article_count`
- `masked_count`
- `run_id`
- `artifact_name`
- `source_commit`
- `imported_at`
- `notes`

Before importing a month, check `取込管理` for an existing `status=success` row for that month. Do not append the same accepted month twice.

## Historical artifact contract

Issue title:

```text
[KEIBAILUKA_HISTORICAL_REQUEST] <request_id>
```

Body:

```json
{
  "start_month": "2024-01",
  "end_month": "2024-12",
  "request_interval_seconds": 0.8,
  "timeout_seconds": 20.0
}
```

`end_month` may be omitted for a one-month request. One request may contain at most 12 months.

Each successful month writes:

- `YYYYMM/keibailuka_month_YYYYMM.csv`: base five columns `日付,会場,R,馬名,コメント`
- `YYYYMM/keibailuka_month_YYYYMM_ledger.csv`: ledger handoff with source metadata and masked flag
- `YYYYMM/month_manifest.json`

The batch root writes:

- `historical_batch_manifest.json`
- `resolved_request.json`
- `run_status.txt`

The workflow returns `KEIBAILUKA_HISTORICAL_RESULT` with the exact `run_id`, `artifact_name`, successful months, failed months and totals.

## Chat-side acceptance and import

No Work thread is required for normal Historical operation.

For each request:

1. Read `KEIBAILUKA_HISTORICAL_RESULT`.
2. Download the exact artifact using `run_id + artifact_name`.
3. Read `historical_batch_manifest.json`.
4. For each month whose own `month_manifest.json` has `validation_status=success`:
   - verify row count and CSV SHA-256 against the month manifest;
   - ensure `日付 + 会場 + R` is unique in the month CSV;
   - ensure the month is not already accepted in `取込管理`;
   - transform each ledger CSV row to the `イルカ明細` columns, adding `key`, `source_run_id`, and `imported_at`;
   - append detail rows;
   - append one `取込管理` success row.
5. A failed month is never imported. If a multi-month request partially fails, successful months may be accepted from that artifact and only failed months are retried.
6. `🤡` rows remain accepted raw data but are counted as unresolved until `馬名_resolved` is filled.

The transfer artifact is disposable after ledger acceptance. The spreadsheet is the canonical accepted ledger.

## Initial backfill plan

Run at most three ordinary Chat requests:

```text
2024-01 .. 2024-12
2025-01 .. 2025-12
2026-01 .. current month
```

If the 2024-2026 sample is insufficient for research, add 2023 with the same workflow; no source-code change is required.

## Comment transport

成功月は `KEIBAILUKA_HISTORICAL_LEDGER_ROWS` Issueコメントにも台帳13列TSVを出力する。最大80行/chunkで、`chunk_index` 順に結合する。これを通常のChat→Google Sheets転記経路とし、artifactはmanifest / SHA監査の根拠として併存させる。

## Concurrency-safe Google Sheets acceptance

Google SheetsへのHistorical受入は **append-only** とする。既存データ末尾の行番号を先に計算して `pasteData` / 固定rowIndexで書き込んではならない。複数Chatスレッドが同じ台帳を同時更新すると、読み取り後に別スレッドが追記した行を上書きするため。

受入手順:

1. 書込み直前に `取込管理` の accepted month と `イルカ明細.key` を再読込する。
2. source monthの全行について、既存 `key` を除いた不足行だけを作る。
3. 不足行は Google Sheets batchUpdate の `appendCells` で `イルカ明細` 末尾へ追加する。
4. `取込管理` も固定行へ書かず、未登録月だけ `appendCells` する。
5. 書込み後に `key` の総件数とunique件数を再読込し、重複0を必須確認する。
6. 同一月の `取込管理.status=success` が既にある場合でも、明細件数がmanifestの `month_row_count` と一致するか確認する。不足があれば source ledger comments / artifactから **不足keyだけ** appendしてrepairする。
7. 競合が起きても既存行を削除・上書きせず、canonical sourceとの集合差分でrepairする。

原則として `pasteData` は新規空シートの初期化以外には使用しない。


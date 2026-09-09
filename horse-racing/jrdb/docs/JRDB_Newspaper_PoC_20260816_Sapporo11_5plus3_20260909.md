# JRDB Newspaper real-data PoC — 2026-08-16 札幌11R 札幌記念

Status: PASS — ANALYSIS-BACKED 5+3 VALIDATED

## Purpose

PACI/Common Readerだけで成立した5走詳細Newspaper PoCを、共有Analysis Liteを補助入力として最大8走まで拡張し、`detailed_recent_history` 5走 + `compact_older_history` 3走の実データ挙動を確認する。

RaceNote bundle / `racenote_*` moduleは入力・依存に使用しない。

## Fixed target

- date: 2026-08-16
- venue: 札幌 (`01`)
- race: 11R
- race name: 札幌記念
- race key: `01261811`
- field size: 16

## PACI baseline

Verified PACI:

- file: `PACI260816.zip`
- size: 558,207 bytes
- SHA-256: `073c7afdf8e3388a5709316d55147a16532a55722b1830a2f0477214546a6370`

PACI-only result:

- 16 horses
- 5 detailed runs per horse
- 80 detailed runs total
- previous expected/resolved/unresolved = 80 / 80 / 0
- target/future chronology violations = 0
- duplicate history identities = 0
- forbidden `racenote_*` imports = 0
- base addons all null / Edge empty

## Analysis Lite

Resolved Drive artifact:

`jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite`

Real workflow audit:

- size: 197,492,736 bytes
- SHA-256: `4df011c74b226ad394a171b71c0841872cb94f3418c8e7f85225a31de89e21b2`
- `PRAGMA quick_check`: `ok`
- `fact_entry_result_lite`: 513,512 rows
- min race date: 2016-01-05
- max race date: 2026-08-23

Newspaper query enforces `race_date < oldest detailed history date`, so target race/result is not eligible for older-history supplementation even though this shared artifact extends beyond the target date.

## Workflow evidence

Issue: `#614 [JRDB_RAW_FETCH_REQUEST] newspaper-poc-sapporo-kinen-20260816-5plus3`

Run:

- run id: `34307352474`
- top-level status: `success`
- `newspaper_poc.audit_status`: `PASS`
- artifact: `jrdb-newspaper-poc-20260816-01-11`

## 5+3 result

All acceptance conditions passed.

- 16/16 horses have exactly 8 history rows
- total history: 128
- `detailed_recent_history`: 80
- `compact_older_history`: 48
- previous expected/resolved/unresolved = 80 / 80 / 0
- Analysis supplemental rows = 48
- chronology violations = 0
- duplicate history identities = 0
- JSON Schema = PASS
- forbidden `racenote_*` imports = 0
- addons all null = true
- Edge all empty = true
- pretty race JSON size: 307,691 bytes
- race JSON SHA-256: `d18a9cddc077ffec8a651a34863d329b742506c1fd304b74b01aaef93f976e42`

## Null distribution

Detailed 80 runs:

- race_name: 3 null
- class_label: 2 null
- last3f_sec: 3 null
- idm: 3 null
- body_weight_kg: 1 null

The notable アドマイヤテラ 2025-11-30 ジャパンC row is `abnormal_code=3`; ZKB race comment states that the horse stumbled immediately after the start, the rider fell, and the race was discontinued. The null time/last3f/IDM values are therefore race-discontinuation semantics, not parser failure.

Compact 48 runs:

- final_win_odds: 48 null
- grade_label: 7 null

`final_win_odds` is null throughout the current Analysis Lite artifact, not only in these 48 rows. Compact history therefore treats popularity as available but win odds as unavailable by source contract. `grade_label` null is allowed for rows that are not represented by the G1/G2/G3/重賞/特別/L mapping.

## Example: アドマイヤテラ

Detailed 1-5:

1. 2026-05-03 京都11R 天皇賞（春） G1 3着
2. 2026-03-22 阪神11R 阪神大賞典 G2 1着
3. 2025-12-28 中山11R 有馬記念 G1 11着
4. 2025-11-30 東京12R ジャパンカップ G1 競走中止
5. 2025-10-05 京都11R 京都大賞典 G2 4着

Compact 6-8:

6. 2025-06-01 東京12R G2 1着 1人気
7. 2025-04-13 阪神10R 特別 1着 1人気
8. 2024-10-20 京都11R G1 3着 7人気

The compact rows intentionally have `race_name=null` because Analysis Lite does not carry race names. Newspaper UI must fall back to class/grade plus venue/R when race name is absent.

## UI interpretation

The 6-8th rows are intentionally `compact_older_history` and do not pretend to contain ZED/ZKB-level detail.

Initial Newspaper rendering policy:

- default visible: 3 detailed runs
- expand: 5 runs
- expand: 8 runs
- 1-5 detailed cells may expose time / last3f / IDM / comments
- 6-8 compact cells show only fields actually available from Analysis
- missing race name falls back to grade/class
- missing compact odds is not rendered as an error

## Decision

P3 real-data data-contract validation is complete. Proceed to P4 Newspaper PWA display PoC using the validated 8-run bundle contract.

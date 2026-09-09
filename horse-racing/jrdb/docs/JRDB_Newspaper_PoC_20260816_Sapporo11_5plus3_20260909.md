# JRDB Newspaper real-data PoC — 2026-08-16 札幌11R 札幌記念

Status: PREPARED FOR ANALYSIS-BACKED 5+3 VALIDATION

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

5-run PACI-only PoC result:

- 16 horses
- 5 detailed runs per horse
- 80 detailed runs total
- previous expected/resolved/unresolved = 80 / 80 / 0
- target/future chronology violations = 0
- duplicate history identities = 0
- forbidden `racenote_*` imports = 0
- base addons all null / Edge empty

## Analysis Lite

GPT standard Drive resolution target:

`jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite`

Expected characteristics from the verified shared artifact:

- table: `fact_entry_result_lite`
- 513,512 rows
- coverage through 2026-08-23
- Newspaper query still enforces `race_date < oldest detailed history date`, so target race/result is not eligible for older-history supplementation.

## 5+3 acceptance

For this race, accept when:

1. all 16 horses remain identity/headcount exact;
2. all PACI detailed 80 runs remain unchanged in source layer/order;
3. Analysis adds up to 3 strictly older rows per horse;
4. no history date is `>= 2026-08-16`;
5. no duplicate `(result_key, race_key, date)` identity is produced;
6. JSON Schema passes;
7. `racenote_*` import remains absent;
8. Analysis provenance (file/size/SHA/quick_check/row count/date span) is recorded by the PoC audit;
9. compact-layer null distribution is recorded separately from detailed-layer null distribution.

## UI interpretation

The 6-8th rows are intentionally `compact_older_history` and do not pretend to contain ZED/ZKB-level detail. Initial Newspaper rendering should continue to prioritize 3 detailed runs; 5/8 expansion changes visible range, not source semantics.

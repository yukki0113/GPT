# JRDB History Access Benchmark 2024

Updated: 2026-09-07

## Purpose

Common Raw history batch API (`jrdb_raw_history.get_horses_runs`) の性能境界を2024実データで確認し、将来Raw履歴アクセスをconsumerへ使う場合に軽量history locator indexを別途必須にする必要があるかを判断する。

現行RaceNote productionはこのAPIを直接利用していない。RaceNoteの履歴は主にPACI / Archive / Analysis Lite経路で構成されるため、本benchmarkは現行RaceNote自体の処理時間改善を示すものではない。

## Test case

- source: `SED_2024.zip`
- target race: 2024-12-28 中山11R (`06245911`)
- runners: 18
- cutoff: `before=2024-12-28` (exclusive)
- requested limit: 8 runs/horse
- actual returned prior runs: 42 total
- all 18 horses had fewer than 8 prior 2024 runs, so Raw traversal scans the full 2024 archive.

## Results

Seven alternating local measurements after warmup:

| method | median |
|---|---:|
| 18 × single-horse annual Raw scan | 1.4709 sec |
| one batch annual Raw scan for 18 horses | 0.0859 sec |
| speedup | 17.13x |

The single-horse and batch Raw results matched for every horse.

Canonical 2024 (`sed_result`, local verified SQLite) returned the same 42 result identities.

| Canonical query | median |
|---|---:|
| 18 horses in one local SQLite query | 0.552 ms |
| 18 indexed per-horse queries in one connection | 0.579 ms |

## Materialization cost context

Published Canonical 2024 transport was revalidated locally:

- ZIP size: 54,815,315 bytes
- ZIP SHA-256: `02f0d665c9bbe43cfb479c6f627f24cf36e9ee3c08e7013ef1bbed43e3e74166`
- payload size: 178,450,432 bytes
- payload SHA-256: `45a7cfb22ddf9840460fe6d3a3681ecc255f16c37071c68f2fa939695b53733b`
- SQLite `integrity_check`: `ok`
- local ZIP extraction median (3 trials): ~0.95 sec
- payload SHA verification median: ~0.11 sec
- SQLite `integrity_check` median: ~1.34 sec

These are local CPU/storage timings only and exclude Drive network transfer.

## Decision

If a one-race consumer chooses direct annual SED Raw history lookup, batch scanning is already sufficiently fast in this 2024 case. The ~85 ms Raw-vs-local-SQLite lookup difference is much smaller than the first-use materialization and transfer cost of the Canonical shard.

Therefore:

- do not add a lightweight history locator index merely because single-horse Raw scans are slow; batch scan removes most of that overhead;
- use `get_horses_runs()` when a consumer actually needs multi-runner direct Raw history access;
- do not migrate current RaceNote history to this API solely for this benchmark result;
- use Canonical annual shards when the workload already benefits from repeated, cross-race, cross-horse, or research queries and the shard is cached;
- keep the Store/Canonical path optional rather than making it a dependency of ordinary Raw history lookup.

This benchmark does not claim that Canonical is unnecessary. It establishes a workload boundary for future consumers: batch Raw is a simple low-overhead option for one-off race history, while Canonical is the preferred materialization for repeated/bulk access.

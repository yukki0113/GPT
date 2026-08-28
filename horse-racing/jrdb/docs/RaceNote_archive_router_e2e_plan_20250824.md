# RaceNote Archive Router 実データ E2E 検証計画

## 対象

- 日付: 2025-08-24
- 会場: 新潟
- R: 11R
- 比較対象:
  - publishable `full_month` RaceNote Archive を `racenote_request.py --archive` で利用する経路
  - 同じ月次生成時に取得した annual Raw cache を利用する historical Raw fallback 経路

## 検証条件

両経路で以下を同一にする。

- GitHub main の同一 commit
- Analysis Lite
- Stats Mart
- target date / venue / race
- stats window = 5 years
- `as_of_exclusive = target_date`

Archive の月次 shard は同一 run 内で annual Raw から再生成し、同一 run 内で Raw fallback にも同じ Raw cache を使う。

## 合格条件

1. Archive Router の `backend_resolution.used_backend == racenote_archive`
2. Raw Router の `backend_resolution.used_backend == historical_raw_cache_or_fetch`
3. Archive shard が `full_month / publishable` として受理される
4. 両経路の最終 RaceNote v1.0 が semantic hash で一致する
5. 比較結果と Router 実行時間を artifact に保存する

byte exact match は参考値とし、`metadata.generated_at` の差を許容する semantic hash を正式比較基準とする。

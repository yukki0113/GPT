# RaceNote v1 production promotion - 2026-08-27

## Decision

5レースPoCと追加検証で固まった履歴・距離・統計・coverage仕様をRaceNote v1.0としてproduction contractへ昇格する。

## Production boundary

```text
PACI
  -> src/racenote_jrdb.py                 # base schema v0.2
  -> src/racenote_history_enrichment.py   # production enrichment
  -> final schema v1.0
```

Request routerのユーザー契約（日付、任意の開催場、任意のR）は変更しない。

## v1.0 fixed policies

- recent_runs: PACI詳細 最大5
- older_runs: Analysis Lite簡略 最大3
- 合計最大8。ただし固定8件・完全な直近8戦ではない
- history coverage scope: `jrdb_jra_history`
- overseas completeness: 推測しない
- exact distanceを保持
- distance ranges: 1000-1400 / 1400-1800 / 1800-2400 / 2500+
- 1400/1800は重複境界
- 2400はmiddle側のみ
- sample size bands: none / small / moderate / sufficient
- stats window: 5 calendar years including target-year YTD
- track condition scope: all_conditions
- as_of_exclusive = target_date
- target-date resultおよび後日結果は使用しない

## Compatibility

base PACI v0.2 fieldsは削除しない。v1.0はenrichment追加後のGPT-facing bundle versionとする。

`recent_runs` / `older_runs` の名称も維持し、意味は `history_coverage.run_layers` で明示する。

## Artifacts

- `schema/racenote_bundle_schema_v1_0.json`
- `src/racenote_history_enrichment.py`
- `docs/README_racenote_v1.md`

旧 `src/racenote_history_enrichment_poc.py` は当面、検証済みengine / regression referenceとして残す。通常実行経路からは外す。

## Remaining internal refactor

production entrypointの外部contractを固定した後、検証済みPoC engineの内部実装をproduction moduleへ統合し、`_poc.py` 依存を解消する。これは出力schemaやrequest contractを変更しない内部リファクタとして扱う。

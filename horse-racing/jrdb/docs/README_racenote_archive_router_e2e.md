# RaceNote Archive Router E2E

`racenote_archive_router_e2e_issue.yml` は、publishable な月次 RaceNote Archive を過去レース Router の preferred backend として利用した場合と、annual Raw fallback を利用した場合の最終 RaceNote を比較する実データ E2E 用 workflow です。

Issue prefix:

```text
[RACENOTE_ARCHIVE_ROUTER_E2E] <request_id>
```

Issue body JSON:

```json
{
  "date": "20250824",
  "venue": "新潟",
  "race": 11,
  "analysis_url": "<Google Drive URL>",
  "mart_url": "<Google Drive URL>"
}
```

同一 run 内で対象月の full-month Archive と annual Raw cache を準備し、同一 Analysis Lite / Stats Mart で Router を2回実行します。

合格条件は、Archive 経路が `racenote_archive`、Raw 経路が `historical_raw_cache_or_fetch` を実際に使用し、最終 RaceNote v1.0 の semantic SHA-256 が一致することです。`metadata.generated_at` のみ semantic hash 対象外です。

これは検証用 workflow であり、日常の RaceNote request 契約を変更するものではありません。

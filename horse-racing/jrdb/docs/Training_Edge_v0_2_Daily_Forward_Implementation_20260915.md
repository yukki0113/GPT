# Training Edge v0.2 — Daily Forward Implementation Status

Date: 2026-09-15

## Implemented

- pre-race daily scorer: `src/score_training_edge_v0_2_daily.py`
- exact five-column Newspaper/PWA handoff
- development percentile display index `0.0-100.0`
- `ROUND_HALF_UP` to one decimal
- complete target-day runner population; frozen-history-ineligible runner remains present with blank index
- raw/unrounded values and eligibility reasons isolated in audit JSON
- formal daily Issue/Actions route: `.github/workflows/jrdb_training_edge_v02_daily_issue.yml`
- target PACI required
- target SED must be absent, otherwise fail closed
- 2010-2025 history + settled 2026 history reconstructed before target scoring
- frozen scientific asset hash checks
- output row/key/one-decimal validation

## Runtime freeze in progress

Before the daily route is declared operationally complete, the fixed 2013-2025 fit population and C/CAB runtime predictions are being fingerprinted under the exact numerical package versions used by the successful 2026 OOT run.

Protocol:

`Training_Edge_v0_2_Runtime_Freeze_Protocol_20260915.md`

The daily route becomes final only after the resulting fingerprint is committed and checked on every daily scoring run.

## Handoff

Final PWA/Newspaper file:

`独自指数_YYYYMMDD.csv`

```csv
date,venue_code,race_no,horse_no,training_edge_index
```

The Newspaper side should perform identity join only and should not recompute, rescale, fill blanks, or re-round the value.

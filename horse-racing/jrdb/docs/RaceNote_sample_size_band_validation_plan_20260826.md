# RaceNote sample size band validation plan - 2026-08-26

Validation targets:

- 2026-05-09 京都11R 京都新聞杯
- 2026-01-05 京都11R 万葉S

Confirm that every summary object retains numeric `starts / wins / top3 / win_rate / top3_rate` and adds a `sample_size_band` derived only from `starts`:

- 0 -> none
- 1-19 -> small
- 20-49 -> moderate
- 50+ -> sufficient

The label is descriptive only and must not alter or suppress statistics.

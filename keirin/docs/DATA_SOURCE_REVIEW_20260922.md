# Keirin Historical source review — 2026-09-22

## Purpose

Paid note output is assumed to contain only proprietary prediction marks/analysis, not copied race tables or source data. Even so, the Historical source must be suitable for automated acquisition and internal commercial analysis.

## Technical availability observed

Historical racecards/results can be reached on multiple public services, including pages around 2016. URL structure and field coverage appear technically sufficient for a 5–10 year warehouse.

## Clearance status

| Source | Historical technical fit | Current clearance decision |
|---|---|---|
| WINTICKET | High | BLOCKED for production bulk source pending explicit permission |
| KEIRIN.JP | High / official | PERMISSION REQUIRED for intended bulk/commercial use |
| OddsPark | High | BLOCKED / PERMISSION REQUIRED |
| Rakuten KDreams | High, especially lineup/comments | PERMISSION REQUIRED |
| Purchased/licensed dataset | Depends on vendor | Preferred if license explicitly permits analysis-derived paid output |

## Minimum permission questions

1. May historical racecard/result data be acquired automatically in a rate-limited manner?
2. May the acquired data be stored long-term in a private database for analysis?
3. May it be used to develop proprietary prediction/scoring logic?
4. May outputs of that logic be sold, provided raw source data is not redistributed?
5. Is attribution required?
6. Are there request-rate, retention, or cache restrictions?
7. Is historical coverage of at least five years available, ideally ten?
8. Are lineup/line information and pre-race comments included/licensable separately?

## PoC acceptance criteria once a source is approved

- freeze source list before fetch
- every discovered race has racecard and result source entries as applicable
- raw bytes saved immutably with SHA-256
- HTTP success/failure captured per item
- retry does not overwrite differing bytes
- independently compare expected race count vs acquired race count
- report missing dates/venues/races explicitly
- target >= 99% coverage before annual expansion; any systematic gap must be explained

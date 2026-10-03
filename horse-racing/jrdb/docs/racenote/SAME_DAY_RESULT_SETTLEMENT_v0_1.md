# RaceNote Same-Day Result / Settlement v0.1

## Purpose

This is the lightweight **post-Freeze same-day settlement path** for RaceNote.
It is intended to answer, on the race day, how the frozen RaceNote marks performed
as fixed 100-yen tickets.

Detailed weekday review remains the JRDB SED/HJC + RaceReview path.  The public-Web
result source here is not a replacement for JRDB post-race analysis and must never
be read before the relevant Forecast Freeze.

## Modules

- `src/racenote_daily_result_fetch.py`
  - default source: Sponichi Keiba Web daily result page
  - one date page -> all detected JRA races
  - retains top 3 finishers and payouts
  - supports repeated execution while racing is still in progress
- `src/racenote_daily_settlement.py`
  - reads a frozen `forecast_YYYYMMDD_all.json` (or compatible records)
  - reads the same-day result JSON
  - generates fixed ticket formations and aggregates ROI
  - emits machine-readable JSON and a compact Markdown report

## 1. Same-day result acquisition

```bash
python horse-racing/jrdb/src/racenote_daily_result_fetch.py \
  --date 2026-10-03
```

Default output:

```text
horse-racing/jrdb/result_cache/20261003_SameDay_Result.json
```

The daily page is parsed into the canonical wager keys:

```text
win
place
frame_quinella
quinella
wide
exacta
trio
trifecta
```

For ordinary non-dead-heat races, winning combinations are reconstructed from the
1st/2nd/3rd horse and frame numbers.  Sponichi's displayed place payout sequence is
mapped in finish order; wide is mapped as 1-2, 1-3, 2-3.

Fail-closed behavior:

- no result yet -> `pending`
- top 3 present but settlement-required payouts are still incomplete -> `pending`
- dead heat / abnormal payout count / non-unique top 3 -> `review_required`
- only `official` races are eligible for automatic settlement

`frame_quinella` is retained when published but is not required by the RaceNote
settlement strategies below.  The settlement-required set is win, place, quinella,
wide, exacta, trio and trifecta.

This module is source-replaceable through the `DailyResultSource` protocol.  v0.1
ships `SponichiDailyResultSource` only.

## 2. RaceNote settlement

```bash
python horse-racing/jrdb/src/racenote_daily_settlement.py \
  --forecast horse-racing/jrdb/backtests/<BTDAY>/<date>/day_merge/forecast_YYYYMMDD_all.json \
  --results horse-racing/jrdb/result_cache/YYYYMMDD_SameDay_Result.json
```

Default outputs:

```text
horse-racing/jrdb/settlement_runs/RaceNote_YYYYMMDD_SameDay_Settlement.json
horse-racing/jrdb/settlement_runs/RaceNote_YYYYMMDD_SameDay_Settlement.md
```

All tickets use a fixed unit stake of **100 yen**.

| Metric | Ticket formation per settled race |
| --- | --- |
| ◎ win | `◎` |
| ◎ place | `◎` |
| quinella | `◎-○`, `◎-▲` |
| exacta | `◎→○`, `◎→▲` |
| trio | `◎` one-horse axis, every 2-horse combination from all other marks |
| trifecta | `◎` fixed 1st, every ordered 2-horse permutation from all other marks |

With the current five-mark Forecast record (`◎ / ○ / ▲ / △1 / △2`), this is:

```text
win       1 ticket
place     1 ticket
quinella  2 tickets
exacta    2 tickets
trio      6 tickets
trifecta 12 tickets
-------------------
total     24 tickets / race
```

For each strategy the JSON/Markdown reports:

- settled race count
- ticket count
- stake
- hit tickets / hit races
- payout
- profit/loss
- return rate
- top payout tickets with venue/R, mark combination, horse-number combination and payout

A `pending` race is not counted as a loss and contributes no stake.  A
`review_required` race is excluded from automatic settlement and makes the CLI exit
non-zero so the exceptional race is not silently incorporated.

## Contamination boundary

The execution order is mandatory:

```text
RaceNote / Forecast
-> Freeze / Guard
-> same-day result acquisition
-> same-day settlement
-> later JRDB SED/HJC detailed review
```

Do not fetch or open target-date same-day results before the Freeze/Guard is complete.
The generated same-day JSON/Markdown files are runtime/post-result artifacts; they are
not prediction inputs and do not need to be committed to Git during routine operation.

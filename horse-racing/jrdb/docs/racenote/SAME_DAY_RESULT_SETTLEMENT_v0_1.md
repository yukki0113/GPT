# RaceNote Same-Day Result / Settlement v0.1

## Purpose

This is the lightweight **post-Freeze same-day settlement path** for RaceNote.
It is intended to answer, on the race day, how the frozen RaceNote marks performed
as fixed 100-yen tickets.

Detailed weekday review remains the JRDB SED/HJC + RaceReview path.  The public-Web
result source here is not a replacement for JRDB post-race analysis and must never
be read before the relevant Forecast Freeze.

## Modules

- `src/racenote_daily_result_from_jrdb.py`
  - preferred source when target-date JRDB post-race Raw is already available
  - SED -> finishers / HJC -> all eight payout types
  - no Web access; cross-validates SED win/place payouts against HJC
- `src/racenote_daily_result_fetch.py`
  - race-day速報 source when target-date SED/HJC is not available yet
  - default source: Sponichi Keiba Web daily result page
  - one date page -> all detected JRA races
  - retains top 3 finishers and payouts
  - supports repeated execution while racing is still in progress
- `src/racenote_daily_settlement.py`
  - reads a frozen `forecast_YYYYMMDD_all.json`, or A/B lane `frozen/records.json`
  - accepts A/B `decision_core.marks=[◎,○,▲,△1,△2]` directly
  - reads the same-day result JSON
  - generates fixed ticket formations and aggregates ROI
  - emits machine-readable JSON and a compact Markdown report

## 1. Result acquisition

Use the cheapest deterministic source already available.

### A. Target-date SED/HJC already acquired — preferred

This is the standard route for next-day / Monday confirmation.

```bash
python horse-racing/jrdb/src/racenote_daily_result_from_jrdb.py \
  --date 2026-10-04 \
  --sed /path/to/SED261004.zip \
  --hjc /path/to/HJC261004.zip \
  --pretty
```

SED supplies finishers and HJC supplies all eight payout types.  The builder also
cross-validates SED win/place payout fields against HJC.  A mismatch fails closed
as `review_required`.

### B. Race-day SED/HJC not available — Web速報 fallback

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

The Web fetch module is source-replaceable through the `DailyResultSource`
protocol.  v0.1 ships `SponichiDailyResultSource` only.  Operationally, however,
JRDB SED/HJC takes precedence whenever both target-date files already exist.

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
| quinella ○ leg | `◎-○` |
| quinella ▲ leg | `◎-▲` |
| quinella combined | `◎-○`, `◎-▲` |
| exacta ○ leg | `◎→○` |
| exacta ▲ leg | `◎→▲` |
| exacta combined | `◎→○`, `◎→▲` |
| trio | `◎` one-horse axis, every 2-horse combination from all other marks |
| trifecta | `◎` fixed 1st, every ordered 2-horse permutation from all other marks |

The ○-leg and ▲-leg rows are analytical views of the same physical quinella/exacta
tickets already included in the combined rows. They do not add stakes or change the
24-ticket formation. They exist so post-race analysis can tell whether ▲ actually
boosted the ◎-anchored payout profile rather than merely selecting a higher-priced horse.

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

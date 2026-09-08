# RaceNote Backtest Settlement Protocol v0.1

## Status

**FROZEN BEFORE TARGET-RACE RESULT / HJC ACQUISITION**

This protocol defines only the initial betting/settlement layer used to evaluate predictions already frozen under `RaceNote_Prediction_Handoff_v0_1.md`.

It does not change RaceNote data, Reader View, prediction marks, confidence, or the provisional prediction logic.

The first evaluation target is the already-frozen file:

```text
prediction_runs/20250824_racenote_prediction_poc_v0_1.json
```

Target races:

- 2025-08-24 新潟7R
- 2025-08-24 中京9R
- 2025-08-24 札幌10R

No target-race result or HJC payout may be used to alter the rules below.

## 1. Unit stake

All tickets are flat-staked at:

```text
100 JPY / ticket
```

No odds-based sizing, confidence sizing, dutching, or post-result adjustment is allowed in v0.1.

## 2. Frozen mark ordering

The authoritative mark order is the `prediction.marks` array in the frozen prediction record.

For settlement purposes:

```text
◎ = first ◎
○ = first ○
▲ = first ▲
△1 = first △ appearing after ▲ in the frozen marks array
```

Additional △ marks remain prediction information but are not used in the v0.1 3連複 ticket construction.

This makes the 4-horse selection mechanical and prevents result-driven choice among multiple △ horses.

## 3. Bet definitions

### Bet 1 — ◎ single win

One win ticket:

```text
◎ 単勝
```

Tickets: 1
Investment per race: 100 JPY

### Bet 2 — ◎ anchored quinella

Two quinella tickets:

```text
◎-○ 馬連
◎-▲ 馬連
```

Tickets: 2
Investment per race: 200 JPY

### Bet 3 — 4-horse trio box

Use exactly these four horses:

```text
◎ / ○ / ▲ / △1
```

Buy the complete 4-horse 3連複 BOX:

```text
C(4,3) = 4 tickets
```

**Important correction to the earlier handoff note:** a 4-horse 3連複 BOX is 4 tickets, not 6. Therefore v0.1 freezes the mathematically correct 4-ticket BOX rather than manufacturing six non-distinct 3-horse combinations.

Tickets: 4
Investment per race: 400 JPY

## 4. Combined evaluation patterns

Evaluate the following six patterns independently:

| Pattern | Included bets | Tickets/race | Investment/race |
|---|---|---:|---:|
| ① | Bet 1 | 1 | 100 JPY |
| ② | Bet 2 | 2 | 200 JPY |
| ③ | Bet 3 | 4 | 400 JPY |
| ①+② | Bet 1 + Bet 2 | 3 | 300 JPY |
| ①+③ | Bet 1 + Bet 3 | 5 | 500 JPY |
| ①+②+③ | Bet 1 + Bet 2 + Bet 3 | 7 | 700 JPY |

Different wager types are settled independently and their payouts are summed within a combined pattern.

## 5. HJC source contract

JRDB HJC is the authoritative payout source.

Use Common Reader:

```text
src/jrdb_raw.py
Parser.hjc(record)
```

Relevant fields:

```text
win[]       # 単勝
quinella[]  # 馬連
trio[]      # 3連複
```

Join by raw 8-byte `race_key_raw`.

SED may be used only as an auxiliary audit of finish/order and must not replace HJC payout values.

## 6. Matching rules

### Win

A win ticket matches an HJC `win` slot when the horse number is identical.

### Quinella

Horse-number order is irrelevant. Normalize both ticket and HJC combination as an unordered two-horse set before matching.

### Trio

Horse-number order is irrelevant. Normalize both ticket and HJC combination as an unordered three-horse set before matching.

### Multiple payout slots / dead heat

Do not collapse HJC slots before matching.

For one purchased ticket, sum every HJC slot that represents the same normalized winning combination. Blank/zero slots contribute zero.

This preserves dead-heat/multiple-payout capacity in the Raw contract.

## 7. Metrics

For each of the six patterns report:

```text
race_count
investment_jpy
payout_jpy
hit_races
hit_rate = hit_races / race_count
return_rate = payout_jpy / investment_jpy
```

`hit_races` is race-level: a race counts as a hit when total payout for that pattern in that race is greater than zero.

Also retain per-race ticket detail for audit, but do not redefine the headline hit rate after seeing results.

## 8. Evaluation discipline

Required sequence:

```text
prediction freeze
 -> settlement protocol freeze
 -> HJC acquisition
 -> deterministic settlement
 -> evaluation report
```

After HJC acquisition begins, do not change:

- prediction marks/order;
- which △ is used;
- ticket construction;
- stake size;
- headline metric definitions.

If the first three races perform poorly, that alone does not invalidate prediction logic. If they perform well, that alone does not validate it. The three-race PoC is an end-to-end settlement check before expanding blinded historical prediction to a materially larger sample.

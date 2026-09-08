# RaceNote Prediction PoC Settlement — 2025-08-24

## Status

**SETTLED AFTER PREDICTION + BETTING RULE FREEZE**

This report settles the three races frozen in `prediction_runs/20250824_racenote_prediction_poc_v0_1.json` using JRDB HJC and `RaceNote_Backtest_Settlement_Protocol_v0_1.md`.

Sequence preserved:

```text
prediction freeze (02355f2a)
 -> settlement protocol freeze (bce2d31e)
 -> HJC fetch (Issue #486 / run 34188799251)
 -> deterministic settlement
```

HJC source: `HJC250824.zip`, SHA-256 `1e40b66620549c503aa06b49480a887d4e4924a7ace95b209f81b6b4be3df36f`; member `HJC250824.txt`, SHA-256 `8a9a32dabd380b8492ce8d0caa728ce009f764cd0357346f72f66a8924d6591f`.

## Frozen bets

- ①: ◎単勝 1点
- ②: ◎-○ / ◎-▲ 馬連 2点
- ③: ◎1頭軸、○▲△1△2への3連複6点
- 100円均等

## Race settlement

| Race | ① win | ② quinella | ③ trio | HJC winning combinations |
|---|---:|---:|---:|---|
| 新潟7R | 0円 | 0円 | 0円 | 単勝 14 / 290円; 馬連 1415 / 1110円; 3連複 091415 / 30250円 |
| 中京9R | 190円 | 630円 | 1500円 | 単勝 10 / 190円; 馬連 0610 / 630円; 3連複 060810 / 1500円 |
| 札幌10R | 0円 | 0円 | 0円 | 単勝 10 / 370円; 馬連 1012 / 1760円; 3連複 071012 / 7180円 |

Only 中京9R hit: ◎10 won, ◎10-○6 quinella hit, and ◎10-○6-▲8 trio hit. 新潟7R and 札幌10R missed all three frozen bet groups.

## Six-pattern summary

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| ① | 300円 | 190円 | 1/3 | 33.33% | 63.33% |
| ② | 600円 | 630円 | 1/3 | 33.33% | 105.00% |
| ③ | 1800円 | 1500円 | 1/3 | 33.33% | 83.33% |
| ①+② | 900円 | 820円 | 1/3 | 33.33% | 91.11% |
| ①+③ | 2100円 | 1690円 | 1/3 | 33.33% | 80.48% |
| ①+②+③ | 2700円 | 2320円 | 1/3 | 33.33% | 85.93% |

## Interpretation

- Three races are too small to accept or reject the prediction logic.
- The settlement pipeline itself is now proven end-to-end: frozen marks -> frozen tickets -> HJC -> deterministic metrics.
- On this tiny sample, ②馬連 alone is the only pattern above 100% return (105.00%); this must not be used to tune v0.1 yet.
- The next valid step is to keep `provisional_handoff_v0.1_unweighted` unchanged and expand blinded historical predictions before comparing segments or modifying prediction weights.

# JRDB Result Cache

## Purpose

This directory is **post-freeze settlement data only**.

It exists so that once HJC has been acquired for a blind-test block, the payouts can be normalized once and reused for later questions such as:

- what if the quinella ticket set changes?
- what if wide is used instead?
- what if exacta / trifecta formations are tested?
- how concentrated are returns by ticket / race / payout tail?

The user is not expected to read these files. They are machine-oriented settlement inputs for GPT / scripts.

## Hard contamination boundary

Prediction generation must not read this directory before the relevant prediction freeze.

Operational order:

1. select target races from retained pre-race / BAC-derived metadata;
2. acquire RaceNote with the target date excluded;
3. generate predictions / comments / betting policies;
4. commit the freeze;
5. only then acquire HJC;
6. normalize HJC into this directory;
7. settle / audit from the normalized result cache.

`prediction_runs/` and RaceNote pre-race inputs are the prediction side.

`result_cache/` is the result side.

Do not join the two until after the freeze commit exists.

## File format

Preferred normalized payout format is CSV with one row per race:

```text
date,venue,race_no,race_key_raw,win,place,frame_quinella,quinella,wide,exacta,trio,trifecta
```

Each payout cell uses:

```text
combination:payout_jpy;combination:payout_jpy;...
```

Examples:

```text
win             12:210
quinella        5-12:1640
trio            5-11-12:35910
trifecta        12-5-11:88140
```

Horse-number order is preserved for ordered bets such as exacta / trifecta. It is only normalized for matching by the settlement code when the wager type is unordered.

All positive HJC slots are retained, including dead-heat / multiple-payout cases.

## Blind-test meaning

A result cache makes later **betting-policy retrospectives** reproducible, but it does not make a race blind again.

Once target results have been exposed in the current working context, the same race must not be presented as a new blind prediction test merely by avoiding this directory. A credible new prediction test uses untouched future/historical target races whose target results have not been opened before the prediction freeze.

For already-settled races, this directory is intentionally safe to use for post-hoc questions about ticket construction, provided any new rule discovered from those results is validated on a later untouched block before promotion.

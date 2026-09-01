# JRDB Ability pre-race feature snapshot v0.1

This package creates the pre-model Ability feature layer on top of audited Index
Base and official RunPerf v0.1. It does not fit, select, or evaluate A0/A1/A2.

```bash
python horse-racing/jrdb/src/build_jrdb_ability_snapshot.py \
  --index-db /path/jrdb_index_base.sqlite \
  --official-runperf-db /path/jrdb_official_runperf.sqlite \
  --out /path/jrdb_ability_snapshot.sqlite
python horse-racing/jrdb/src/audit_jrdb_ability_snapshot.py \
  --db /path/jrdb_ability_snapshot.sqlite --out /path/ability_snapshot_audit.json
```

One row is retained for every `runner_pre` target, including debut horses. History
is date-batched and every source date is strictly earlier than the target date;
same-day completed results cannot affect another target snapshot. The database
keeps all recency (`0.70/0.80/0.90/1.00`) and distance-bandwidth
(`200/400/600/800m`) candidates without choosing one.

Target race information is limited to `PRE_RACE` runner context. A
`CURRENT_RESULT_FALLBACK` context is explicit and not validated as PRE_RACE.
Target labels are stored only in `ability_current_result`, separately from
features. Odds, popularity and market columns are absent.

There is no verified historical PRE_RACE target-going field in the current Index
Base source contract. Therefore `going_fit` remains present but NULL/missing,
with `UNAVAILABLE_NO_VERIFIED_PRE_RACE_TARGET_GOING`; target SED final going is
never used as a substitute.

Jockey residuals use a transparent past-only horse baseline: the mean of up to
the previous five scored official RunPerf rows before each historical ride.
Rides lacking that baseline are counted as unavailable and excluded from the
residual mean. No shrinkage is selected here.

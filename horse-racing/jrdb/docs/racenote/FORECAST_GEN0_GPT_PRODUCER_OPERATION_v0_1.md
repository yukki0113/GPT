# RaceNote Forecast Gen0 GPT Producer Operation v0.1

Status: IMPLEMENTED / FULL-DAY HISTORICAL E2E PASS

`racenote_forecast_gen0_producer.py` is the explicit boundary between a
RaceNote v1.0 bundle and the existing Gen0 validation/freeze implementation.
It is not a scorer and never derives marks, ranks, probabilities, or weights.

## Data boundary

1. Build the isolated `INDEPENDENT` view through
   `racenote_gen0_2_input_firewall.py`.
2. Give that hash-addressed view to the approved GPT prediction execution.
3. Save GPT's structured decision as a candidate.
4. Materialize it with `racenote_forecast_gen0_producer.py`.
5. Freeze only the resulting candidate with `racenote_forecast_gen0.py`, then
   run `racenote_forecast_gen0_guard.py` against the original RaceNote runners.

The producer verifies all source runner identities and source hashes before it
emits a candidate.  It rejects substitutions, missing runners, consensus,
market, result, or payout fields through the firewall and Gen0 validation.

## Command

```bash
python src/racenote_forecast_gen0_producer.py \
  --bundle ./racenote/20181202/中山_01.json \
  --decision ./gpt/20181202_中山_01_decision.json \
  --created-at 2018-12-02T08:00:00+09:00 \
  --request-output ./gpt/request.json \
  --candidate-output ./gpt/candidate.json
```

The `--decision` file is a structured response from the approved GPT execution,
not a fallback score.  It must contain all Gen0 fields required by
`FORECAST_GEN0_PREDICTION_CONTRACT_v0_1.md`, plus `race_key` and `artifact_ref`.

## Operational restriction

For a historical E2E, first materialize the accepted Warehouse generation and
produce RaceNote with `used_backend=historical_warehouse`. Historical
enrichment uses the canonical Analysis input only. Rolling horse/sire/jockey/
frame statistics are calculated directly from Analysis with
`race_date < target_date`; Stats Mart is a frozen legacy cache and is not an
active RaceNote dependency.

A missing approved GPT execution, missing canonical Analysis input, or any
input identity mismatch is a fail-closed E2E failure. It must not fall back to
a legacy scorer, fixed weights, Raw (except the documented pre-2010 boundary),
or a fixture and be reported as PASS.

The 2018-12-02 operational full-day E2E passed 36 races / 501 runners through
INDEPENDENT request generation, GPT decision materialization, producer,
validator, freeze/hash audit, source-runner guard, day-package generation, and
the strict Newspaper/PWA identity handoff audit. Evidence is recorded in
`RaceNote_Operational_E2E_20181202_20260923.md`.

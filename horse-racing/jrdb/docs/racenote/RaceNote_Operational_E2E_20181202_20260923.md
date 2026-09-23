# RaceNote Operational E2E — 2018-12-02

Status: **PRE-FLIGHT PASS / FULL-DAY GPT DECISION PENDING**

Implementation commit: `38ae2bab688e4614404b5f0cf1c4be9060e7d617`

## Inputs

- Historical Warehouse generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- Warehouse pointer: `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`
- Base backend: `historical_warehouse` (Archive was explicitly bypassed)
- Analysis source: canonical Analysis Parquet materialized to SQLite, then an as-of projection with all historical rows strictly before `2018-12-02` and target-day identity fields only.
- Stats Mart: generated from the same pre-target projection.

The as-of projection audit reported 144,332 historical rows, 501 target identity rows, zero target-day result-bearing values, and SQLite integrity `ok`.

## Executed evidence

### One-race operational pre-flight — 中山1R

- `used_backend`: `historical_warehouse`
- race key: `06185201`
- runners: 16/16
- RaceNote history enrichment: warning count 0; `as_of_exclusive=2018-12-02`
- GPT route: ChatGPT Work read the hash-addressed independent view and supplied a structured decision. No API key, scorer, fixed weight, market input, target result, or Raw fallback was used.
- producer binding, freeze/hash audit, and source-runner completeness guard: **PASS**
- frozen prediction hash: `f213ad47c553e9c9bf8f05516f0924d9f51a78f768966e6039b456169c71c656`
- PWA handoff: the existing strict RaceNote handoff loader accepted all 16 rows, identity/rank/mark/SHA checks included.

The worktree evidence is under `.racenote_e2e/one-race-20181202-r5-rekey2/operational_preflight/`.

### Full-day data plane — 2018-12-02

- bundle count: 36
- runner count: 501
- history-enrichment warnings: 0
- all bundles: Warehouse backend, accepted-generation input, race-key present, and `as_of_exclusive=2018-12-02`
- independent firewall request artifacts: 36/36

The full-day evidence is under `.racenote_e2e/full-day-20181202-production/20181202/`.

## Consumer identity fix

`race.race_key` is now preserved from the parser-owned `race_key_raw` in the
RaceNote normalized race object. This is a transparent identity field, not a
new feature or changed prediction semantic. It enables the existing Newspaper
strict merge contract to cross-check `race_key` rather than accepting a guessed
identity.

## Boundary check

`racenote_request.py --date 20260922 --today 20260922 --plan-only` resolved
`base_backend=paci`. Therefore the 2026 daily PACI route is unchanged and
cannot request the 2010–2025 Warehouse.

## Remaining required execution

The 36 full-day independent request artifacts are intentionally not converted
into synthetic decisions. Each must receive an actual approved GPT structured
decision before producer/freeze/guard and the complete-day Newspaper merge can
be marked PASS. A local rule, legacy scorer, or fixed-weight substitute is
prohibited by the Gen0 contract.

Accordingly this report is not an `HISTORICAL_WAREHOUSE_OPERATIONAL_CUTOVER`
claim. The data plane and one-race operational pre-flight pass; full-day GPT
prediction, freeze, and consumer merge remain pending real decisions.

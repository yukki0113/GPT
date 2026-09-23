# RaceNote Operational E2E — 2018-12-02

Status: **FULL-DAY E2E PASS / HISTORICAL CUTOVER PASS / RESEARCH RESTART GO**

Implementation head: `9822c674731c26cc2d3c08cc385b78ce23c7bbda`

## Inputs

- Historical Warehouse generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- Warehouse pointer: `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`
- Base backend: `historical_warehouse` (Archive was explicitly bypassed)
- Analysis source: canonical Analysis Parquet materialized to SQLite, then an as-of projection with all historical rows strictly before `2018-12-02` and target-day identity fields only.
- Stats Mart: **not required**. It is a frozen legacy cache and is not part of the active RaceNote path.

The as-of projection audit reported 144,332 historical rows, 501 target identity rows, zero target-day result-bearing values, and SQLite integrity `ok`. Rolling horse/sire/jockey/frame statistics are derived directly from Analysis with `race_date < target_date`.

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

## Full-day GPT Forecast E2E — PASS

GitHub Actions run: `35847351773`

Head commit: `9822c674731c26cc2d3c08cc385b78ce23c7bbda`

Final artifact: `racenote-20181202-full-day-final-e2e`

Artifact digest:
`sha256:cf22326fdd6ed79946503729e553041a809a7602f35e17dc77a5ec7f74b3aa52`

Verified results:

- race count: 36/36
- runner count: 501/501
- missing race: 0
- duplicate race: 0
- orphan race: 0
- runner missing: 0
- runner duplicate: 0
- INDEPENDENT requests: 36/36
- producer / validator / freeze / hash audit / source-runner guard: PASS
- frozen forecasts: 36/36
- prediction hash recomputation: 36/36 match
- evaluation mode: `BLINDED_HISTORICAL`
- result visibility: `HIDDEN` for all 36 races
- Newspaper/PWA strict identity handoff audit: PASS
- Stats Mart required: false
- historical backend: `historical_warehouse`

Final operational claims:

```text
HISTORICAL_WAREHOUSE_OPERATIONAL_CUTOVER=PASS
RACENOTE_FORECAST_ONE_RACE_PREFLIGHT=PASS
RACENOTE_FORECAST_FULL_DAY_E2E=PASS
RACENOTE_RESEARCH_RESTART=GO
```

The active historical path is therefore:

`Historical Warehouse -> Analysis canonical -> RaceNote -> INDEPENDENT firewall -> GPT decision -> producer/validator -> freeze/guard -> day-package -> Newspaper/PWA handoff`

Stats Mart remains only as a frozen legacy asset and must not be rebuilt or
treated as an active dependency for RaceNote.

## CI note

The RaceNote Warehouse compatibility test passed on the E2E head. The remaining
Common Reader failures are outside this cutover result and are tracked
separately: BAC/SED legacy projection differences for `win5_leg_no=None`, and
a Raw adapter test fixture missing `ZED_2024.zip`. They do not invalidate the
36R/501-runner RaceNote full-day E2E result.

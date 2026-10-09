# RaceNote v0.5.2 Single-Day Runbook v0.1

Status: **CURRENT BASELINE OPERATION — NON-A/B**
Date: 2026-10-07
Logic: `RaceNote-Human-Context-Reader-0.5.2-candidate`

## Purpose

This is the ordinary prospective RaceNote path after the BTDAY-0057..0060
v0.5.1/v0.5.2 comparison.

The input source depends on the target year:

- **2026:** existing daily PACI ZIP → `racenote_v052_from_paci.py` (unchanged default).
- **2010–2025:** accepted Historical Warehouse →
  `racenote_v052_from_historical_warehouse.py`, after the Raw/Warehouse
  v0.5.2 equivalence report says `PASS`.

Both sources converge at the same DAY PREP, forecast_prep, v0.5.2 Reader,
Decision Core, Freeze and Verify contracts.

A/B session creation, sibling lanes and a two-lane Freeze barrier are not
required.

The operational shape is:

```text
2026 PACI ZIP or 2010–2025 accepted Historical Warehouse
  -> RaceNote daily build
  -> market-blind forecast_prep
  -> one sealed v0.5.2 Reader set
  -> model authors v0.5.2 Decision Cores
  -> venue save
  -> immutable single-day Freeze
  -> verify
  -> publication / later settlement
```

Target results, target final odds/popularity and payouts remain forbidden until
the single-day Freeze is complete.

## BTDAY lottery source routing

The canonical lottery state remains the legacy-named file:

`horse-racing/jrdb/config/racenote_backtest_day_pool_2026.json`

Despite the filename, it is now the unified first-cycle clean-blind state for:

- **2026** daily PACI rows (`source_mode` omitted/treated as `paci`);
- **2025** accepted Historical Warehouse rows (`source_mode=historical_warehouse`,
  `source_reference=jrdb_normalized_warehouse_v1_2010_2025_g20260921`,
  `selection_cycle=1`).

The 2025 inventory is derived from the actual `BAC_2025.zip` member dates
(109 JRA race days), not from a guessed weekend calendar. A normal unfiltered
`pick` therefore samples from both remaining 2026 PACI days and unused 2025
Historical days:

```bash
python horse-racing/jrdb/src/racenote_backtest_day_picker.py pick \
  --state horse-racing/jrdb/config/racenote_backtest_day_pool_2026.json \
  -n 1
```

After reservation, inspect the selected row's `source_mode`; do not assume a
`paci_file_id` exists.

- `paci` -> keep the existing 2026 `racenote_v052_from_paci.py` route.
- `historical_warehouse` -> use the Historical prepare route below. The request /
  temporary orchestration must carry `source_mode`, `source_reference`, target
  date and reservation seed instead of inventing a PACI file id.

For an explicitly Historical-only draw, use
`--source-mode historical_warehouse --selection-cycle 1`. Do not clear used
flags to replay a date; add a later selection cycle instead.


## 2010–2025 Historical Warehouse prepare

### Materialize the accepted public Drive inputs first

For the accepted 2025 Historical route, do not add ad-hoc `gdown` URLs to a
BTDAY workflow. Use the reviewed manifest and the shared unauthenticated
read-only helper introduced by Drive routing decision v0.2:

```bash
python tools/gpt_io/public_drive/fetch.py \
  --manifest horse-racing/jrdb/config/public_drive/racenote_historical_golden_20251228_v1.json \
  --output-root <historical-input-root> \
  --receipt <historical-input-root>/public_drive_fetch_receipt.json
```

The helper is the canonical `gdown` transport boundary: every file id is
repository-reviewed, SHA-256 pinned, downloaded read-only, and promoted locally
only after integrity validation. Direct workflow `gdown`, ad-hoc
`drive.google.com` URLs, authenticated fallback and Drive writes remain
prohibited.

Use the resulting local `warehouse/`, Analysis and RaceReview assets with the
Historical command below. The committed equivalence PASS report is a generation
gate; the target BTDAY date does not need to equal the golden-day date.

The accepted Warehouse pointer and local immutable assets must match the
generation in
`RACENOTE_HISTORICAL_WAREHOUSE_V052_EQUIVALENCE_20251228.json`.
The prepare command rejects a missing/FAIL report, another generation, a
target year outside 2010–2025, or an existing output root.

```bash
python horse-racing/jrdb/src/racenote_v052_from_historical_warehouse.py \
  --date YYYY-MM-DD \
  --selection-id BTDAY-XXXX \
  --main-sha <full-main-SHA> \
  --equivalence-report horse-racing/jrdb/docs/racenote/RACENOTE_HISTORICAL_WAREHOUSE_V052_EQUIVALENCE_20251228.json \
  --warehouse-current <accepted-warehouse-root>/current.json \
  --warehouse-asset-root <accepted-warehouse-root> \
  --analysis-root <verified-analysis-current-root> \
  --racereview-root <verified-racereview-generation-root> \
  --binding horse-racing/jrdb/config/racenote_reader_v050_binding.json \
  --policy horse-racing/jrdb/docs/racenote/research-work/results/stage_c/reader_feature_policy_v0_5_candidate.json \
  --output-root <new-immutable-operation-root>
```

This writes `day_prep`, `forecast_prep`, `v052/session.json`,
`v052/reader_manifest.json`, `v052/reader/*.json`, and
`operation_handoff.json`. Require `SESSION_SEALED`, `market_blind=true`,
`result_opened=false`, `target_market_opened=false`, and
`as_of_exclusive=target_date` before authoring. Continue with the existing
`racenote_v052_single_day.py save`, `freeze` and `verify` steps below. Open
target results only after Freeze/Verify succeeds.

For a historical date pool, use the existing
`racenote_backtest_day_picker.py` with inventory rows such as:

```json
{"date":"2025-12-28","source_mode":"historical_warehouse","source_reference":"jrdb_normalized_warehouse_v1_2010_2025_g20260921","selection_cycle":1,"eligible":true,"exclusion_reason":null}
```

`pick --source-mode historical_warehouse --selection-cycle 1` selects first
blind turns. Add `selection_cycle: 2` as a new inventory row only after the
first turn is used; `pick --selection-cycle 2` preserves the first-cycle
selection and usage history. The picker state records source reference,
cycle, eligibility and selection ID. A 2010 day whose previous-result keys
precede Warehouse coverage fails closed; the explicit Raw boundary fallback
in `racenote_request.py` remains a separate audit/rollback procedure.

## 1. TURN 1 — DAY PREP / prediction-thread orchestration responsibility

The **prediction thread owns the entire pre-result operation from PACI through Verify** when the user asks for a day's prediction.

TURN 1 and TURN 2 are internal phases of the same prediction request, not separate threads.

The prediction thread must:
- acquire or resolve the target PACI;
- run/route Analysis and RRDB enrichment;
- build the daily RaceNote package;
- create the market-blind forecast_prep;
- create the sealed v0.5.2 Reader/session;
- then continue into race-by-race authoring, Freeze and Verify.

If the current local runtime lacks DuckDB or another required dependency, the prediction thread must **route TURN 1 through an execution environment that supports the canonical pipeline** rather than omit the stage or create a provisional Reader/Freeze.

The analysis/research thread is not a prerequisite for ordinary daily prediction. Its normal responsibilities are date reservation, post-race settlement, research aggregation and logic development.

Before authoring begins, the following handoff must exist:

```text
<output-root>/operation_handoff.json
<output-root>/forecast_prep/
<output-root>/v052/session.json
<output-root>/v052/reader_manifest.json
<output-root>/v052/reader/*.json
```

Required handoff state:

- `status=READY_FOR_V052_AUTHORING`
- `market_blind=true`
- `result_opened=false`
- canonical v0.5.2 Reader/session materialized

The prediction thread's TURN 1 orchestration may use the PACI entrypoint below.

Historical BTDAY:

```bash
python horse-racing/jrdb/src/racenote_v052_from_paci.py \
  --date YYYY-MM-DD \
  --paci /path/to/PACIyymmdd.zip \
  --selection-id BTDAY-XXXX \
  --main-sha <40-char-main-sha> \
  --analysis-root <canonical-analysis-root> \
  --racereview-current-cache <rrdb-current-cache> \
  --output-root horse-racing/jrdb/backtests/BTDAY-XXXX/YYYYMMDD/v052_day
```

Normal forward day:

```bash
python horse-racing/jrdb/src/racenote_v052_from_paci.py \
  --date YYYY-MM-DD \
  --paci /path/to/PACIyymmdd.zip \
  --selection-id DAILY-YYYYMMDD \
  --main-sha <40-char-main-sha> \
  --analysis-root <canonical-analysis-root> \
  --racereview-current-cache <rrdb-current-cache> \
  --output-root horse-racing/jrdb/daily/YYYYMMDD/v052_day
```

`--racereview-root` may be used instead of `--racereview-current-cache`.

The command performs:

1. `build_racenote_daily.py` equivalent day build;
2. `racenote_prepare_forecast_input.py` market stripping/binding;
3. v0.5.2 normal_view derivation;
4. a sealed one-lane session.

Required final handoff status:

`READY_FOR_V052_AUTHORING`

and:

- `ab_required=false`;
- `market_blind=true`;
- `result_opened=false`.


### Canonical BTDAY TURN 1 execution route

For GitHub-backed BTDAY preparation, the canonical workflow is:

`/.github/workflows/racenote_btday_v052_prepare.yml`

It must call `racenote_v052_from_paci.py` as the v0.5.2 TURN 1 entrypoint so that one request produces all of:

- validated daily RaceNote manifest / validation report;
- market-blind `forecast_prep`;
- sealed `v052/session.json`;
- `v052/reader_manifest.json` and `v052/reader/*.json`;
- `operation_handoff.json` with `READY_FOR_V052_AUTHORING`.

The legacy-named `racenote_btday_v046_prepare.yml` is retired from ordinary operation. Although its RaceNote contents were already generated by `build_racenote_daily.py`, it stopped at `forecast_prep` and did not materialize the complete v0.5.2 authoring session.

## 2. TURN 2 — model authoring responsibility

After TURN 1 reaches `READY_FOR_V052_AUTHORING`, the same prediction thread changes phase from mechanical preparation to model judgment.

It must not:
- bypass a failed TURN 1;
- create an alternative/provisional Reader;
- invent a provisional Freeze status when canonical input is unavailable;
- silently omit Analysis/RRDB enrichment.

If the canonical handoff is not ready, repair or reroute TURN 1 before authoring. Do not proceed with a degraded prediction input.

## 2.1 Authoring input

Only read:

```text
<output-root>/v052/reader/*.json
<output-root>/v052/reader_manifest.json
<output-root>/v052/session.json
```

Do not use:

- target-day result files;
- target final market;
- an old v0.5.1/v0.5.2 sibling prediction;
- prior BTDAY marks as prediction evidence.

Follow the promoted v0.5.2 contract:

`FORECAST_HUMAN_CONTEXT_READER_v0_5_2_CANDIDATE.md`

The Decision Core must retain:

- protected `ordinary_five`;
- `WIN_FIRST_NOT_PLACE_FIRST` ◎ selection;
- `ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK` ▲ mode;
- audited six-to-five compression.

## 2.2 Decision Core prose recording (2026-10-09; no prediction change)

After the ordinary v0.5.2 judgment is complete, record the reasoning under
section 4.1 of `FORECAST_HUMAN_CONTEXT_READER_v0_5_2_CANDIDATE.md` and the
reader-facing contract in `FORECAST_READER_FACING_PROSE_v0_1.md`.

This is still the same prediction. The explanation fields are a faithful record
of that prediction, not a second scoring pass.

The important operational principle is that the written record should preserve
the real shape of the comparison. A materially stronger ◎ case should remain
materially stronger because of the race evidence that supports it. A marginal
◎/○ ordering should remain visibly marginal. A conditional winning route
should retain its condition. The prose should not strengthen, flatten or
sanitize the judgment merely because a later research process may classify the
frozen explanation.

Use the existing Decision Core shape unchanged. `race_model`,
`honmei_win_case`, `second_case`, `ranking_reason`,
`boundary_review.reason`, `candidate_compression.reason`,
`mainline_cases` and `single_shot_case` each keep their existing semantic
roles. They should form one internally consistent account of the race rather
than independent text boxes written to satisfy separate wording rules.

`reader_facing_reason` is the same judgment compressed into natural newspaper
prose. It should not copy audit text mechanically, but it also must not tell a
different story about the relative strength of ◎ and ○.

Card-level review remains prose-only: remove interchangeable boilerplate where
it hides different reasoning, but leave genuinely similar races similar.
Marks, candidate membership, role assignment, Reader evidence and Step E are
not reopened during this review.

Older FROZEN outputs remain immutable. Provenance identifies which authoring
guidance produced each cohort.

## 3. Save each venue

Place one full venue Decision Core array at:

```text
<output-root>/v052/incoming/<venue>.json
```

Then:

```bash
python horse-racing/jrdb/src/racenote_v052_single_day.py save \
  --root <output-root>/v052 \
  --decisions <output-root>/v052/incoming/<venue>.json
```

Save is immutable per venue. A second materially different write must not
silently replace an authored venue.

## 4. Freeze the day

After all expected venues have been saved:

```bash
python horse-racing/jrdb/src/racenote_v052_single_day.py freeze \
  --root <output-root>/v052
```

Required status:

`FROZEN_CLEAN_BLIND`

Freeze produces:

```text
v052/frozen/
  records.json
  day_handoff.json
```

No A/B barrier is required.

## 5. Verify before publication or settlement

```bash
python horse-racing/jrdb/src/racenote_v052_single_day.py verify \
  --root <output-root>/v052
```

Verification re-checks:

- sealed forecast_prep identity;
- Reader hashes;
- race/horse roster;
- all authored Decision Core hashes;
- v0.5.2 Decision Core validation;
- frozen record binding;
- `market_blind=true`;
- `result_opened=false`.

Only after verify succeeds may downstream publication consume the Freeze.

Historical BTDAY settlement may open results only after this point.

## 6. Existing A/B infrastructure

The following remain valid for historical reproduction and new research when a
real two-version comparison is desired:

- `racenote_ab_session.py`
- `racenote_ab_lane.py`
- `racenote_ab_freeze_barrier.py`
- `RACENOTE_CLEAN_BLIND_V051_V052_AB_RUNBOOK_v0_1.md`

They are not required for normal v0.5.2 operation.

## 7. Operational principle

v0.5.2 is now the baseline, not merely one lane of an experiment.

Therefore the default mental model is:

```text
PACI -> one evidence package -> one v0.5.2 judgment -> one immutable Freeze
```

A/B machinery should be introduced only when there are actually two competing
forecast contracts to compare.

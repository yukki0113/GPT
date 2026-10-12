# RaceNote v0.5.3 Single-Day Runbook v0.1

Status: **CURRENT CANDIDATE OPERATION — REBUILT R2 / NON-A/B**
Date: 2026-10-12
Logic: `RaceNote-Human-Context-Reader-0.5.3-candidate`
Contract revision: `v053-boundary-safety-r2`

## Purpose

This is the prospective single-day candidate path derived from the promoted v0.5.2 baseline.
No v0.5.1/v0.5.3 A/B comparison is claimed.

The 2026-10-12 rebuild narrows v0.5.3 back to **v0.5.2 + boundary safety**.
New sessions are bound to `contract_revision=v053-boundary-safety-r2`.
Pre-rebuild v0.5.3 sessions without that field remain immutable audit evidence.
BTDAY-0077 and BTDAY-0078 are closed unprocessed and are not r2 performance evidence.

The input source depends on the target year:

- **2026:** existing daily PACI ZIP → `racenote_v053_from_paci.py` (unchanged default).
- **2010–2025:** accepted Historical Warehouse →
  `racenote_v053_from_historical_warehouse.py`, after the Raw/Warehouse
  v0.5.2 equivalence report (reused because the v0.5.3 Reader evidence projection is unchanged) says `PASS`.

Both sources converge at the same DAY PREP, forecast_prep, v0.5.3 Reader,
Decision Core, Freeze and Verify contracts.

A/B session creation, sibling lanes and a two-lane Freeze barrier are not
required.

The operational shape is:

```text
2026 PACI ZIP or 2010–2025 accepted Historical Warehouse
  -> RaceNote daily build
  -> market-blind forecast_prep
  -> one sealed v0.5.3 Reader set
  -> model authors v0.5.3 Decision Cores
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

- `paci` -> keep the existing 2026 `racenote_v053_from_paci.py` route.
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
python horse-racing/jrdb/src/racenote_v053_from_historical_warehouse.py \
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

This writes `day_prep`, `forecast_prep`, `v053/session.json`,
`v053/reader_manifest.json`, `v053/reader/*.json`, and
`operation_handoff.json`. Require `SESSION_SEALED`, `market_blind=true`,
`result_opened=false`, `target_market_opened=false`, and
`as_of_exclusive=target_date` before authoring. Continue with the existing
`racenote_v053_single_day.py save`, `freeze` and `verify` steps below. Open
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
- resolve the reserved BTDAY source mode;
- for 2026, acquire/resolve the target PACI; for 2010–2025, materialize the accepted Historical Warehouse bundle;
- run/route Analysis and RRDB enrichment;
- build the daily RaceNote package;
- create the market-blind forecast_prep;
- create the sealed v0.5.3 Reader/session;
- then continue into race-by-race authoring, Freeze and Verify.

If the current local runtime lacks DuckDB or another required dependency, the prediction thread must **route TURN 1 through an execution environment that supports the canonical pipeline** rather than omit the stage or create a provisional Reader/Freeze.

The analysis/research thread is not a prerequisite for ordinary daily prediction. Its normal responsibilities are date reservation, post-race settlement, research aggregation and logic development.

Before authoring begins, the following handoff must exist:

```text
<output-root>/operation_handoff.json
<output-root>/forecast_prep/
<output-root>/v053/session.json
<output-root>/v053/reader_manifest.json
<output-root>/v053/reader/*.json
```

Required handoff state:

- `status=READY_FOR_V053_AUTHORING`
- `market_blind=true`
- `result_opened=false`
- canonical v0.5.3 Reader/session materialized
- `v053/session.json.contract_revision=v053-boundary-safety-r2`

The prediction thread's TURN 1 orchestration must branch by the reserved
`source_mode`.

Historical BTDAY (2010–2025) uses the Historical Warehouse entrypoint documented
in the preceding section:

```bash
python horse-racing/jrdb/src/racenote_v053_from_historical_warehouse.py \
  --date YYYY-MM-DD \
  --selection-id BTDAY-XXXX \
  --main-sha <40-char-main-sha> \
  --equivalence-report horse-racing/jrdb/docs/racenote/RACENOTE_HISTORICAL_WAREHOUSE_V052_EQUIVALENCE_20251228.json \
  --warehouse-current <historical-input-root>/warehouse/current.json \
  --warehouse-asset-root <historical-input-root>/warehouse \
  --analysis-root <historical-input-root>/analysis \
  --racereview-root <historical-input-root>/rrdb/postrace_review/v0_1 \
  --binding horse-racing/jrdb/config/racenote_reader_v050_binding.json \
  --policy horse-racing/jrdb/docs/racenote/research-work/results/stage_c/reader_feature_policy_v0_5_candidate.json \
  --output-root horse-racing/jrdb/backtests/BTDAY-XXXX/YYYYMMDD
```

Normal 2026 / forward PACI day:

```bash
python horse-racing/jrdb/src/racenote_v053_from_paci.py \
  --date YYYY-MM-DD \
  --paci /path/to/PACIyymmdd.zip \
  --selection-id DAILY-YYYYMMDD \
  --main-sha <40-char-main-sha> \
  --analysis-root <canonical-analysis-root> \
  --racereview-current-cache <rrdb-current-cache> \
  --output-root horse-racing/jrdb/daily/YYYYMMDD/v053_day
```

`--racereview-root` may be used instead of `--racereview-current-cache`.

The command performs:

1. `build_racenote_daily.py` equivalent day build;
2. `racenote_prepare_forecast_input.py` market stripping/binding;
3. v0.5.3 normal_view derivation;
4. a sealed one-lane session.

Required final handoff status:

`READY_FOR_V053_AUTHORING`

and:

- `ab_required=false`;
- `market_blind=true`;
- `result_opened=false`.


### GitHub-backed BTDAY TURN 1

v0.5.3 prediction logic is implemented independently of transport orchestration.
Do not clone the legacy v0.5.2 workflow blindly: current Drive routing forbids
ad-hoc Actions-to-Drive transport. Until a v0.5.3 Actions route is separately
reviewed, materialize canonical inputs through the approved GPT/native Drive or
reviewed public-drive helper path and invoke the v0.5.3 entrypoints above.

## 2. TURN 2 — model authoring responsibility

After TURN 1 reaches `READY_FOR_V053_AUTHORING`, the same prediction thread changes phase from mechanical preparation to model judgment.

It must not:

- bypass a failed TURN 1;
- create an alternative/provisional Reader;
- invent a provisional Freeze status when canonical input is unavailable;
- silently omit Analysis/RRDB enrichment;
- consult prior BTDAY marks or a sibling forecast.

If the canonical handoff is not ready, repair or reroute TURN 1 before authoring. Do not proceed with a degraded prediction input.

### 2.1 Authoring input

Only read:

```text
<output-root>/v053/reader/*.json
<output-root>/v053/reader_manifest.json
<output-root>/v053/session.json
```

Do not use target results, target final market, prior v0.5.3 outputs, or earlier BTDAY marks as prediction evidence.

Follow:

`FORECAST_HUMAN_CONTEXT_READER_v0_5_3_CANDIDATE.md`

### 2.2 r2 judgment procedure

The r2 procedure deliberately restores the v0.5.2 separation.

1. **Race model** — read the complete Reader and form the race structure.
2. **Ordinary five** — author an ordered protected five before searching for an outside shot.
3. **◎ / ○** — choose both only inside the ordinary five using `WIN_FIRST_NOT_PLACE_FIRST`.
4. **External challenger** — choose exactly one outside horse with a genuinely asymmetric win route.
5. **Fixed boundary comparison** — expose only the lowest-ranked non-anchor horse in the already-authored ordinary five.

The Step E presumption is `KEEP_ORDINARY_FIVE`.

A challenger is not admitted merely because it supplies a different running style or makes the five-horse set more diverse. Route uniqueness qualified the horse for Step D; it is not an exchange bonus in Step E.

Use `ADMIT_CHALLENGER` only when current-condition-relevant Reader evidence makes the challenger genuinely competitive with the fixed boundary horse even before route diversity is considered. If that comparison is ambiguous, KEEP.

Do not search the ordinary five for another horse that is easier to remove.

For r2 sessions the validator mechanically rejects ADMIT when `excluded_horse_no` is not the lowest-ranked non-anchor horse from `ordinary_five`.

### 2.3 Decision Core recording

Record the completed judgment once. Recording is not another prediction pass.

Keep field roles separate:

- `race_model`: compact race structure;
- `honmei_win_case` / `second_case` / `ranking_reason`: ◎ versus ○ only;
- `external_challenger_case`: why the outside horse qualifies for asymmetric review;
- `boundary_review.reason`: challenger versus the fixed ordinary boundary horse;
- `candidate_compression.reason`: final KEEP / ADMIT conclusion;
- `mainline_cases` / `single_shot_case`: final five-horse role structure;
- `reader_facing_reason`: compact natural-language summary.

Do not put ▲ selection into `ranking_reason`.

Do not copy `race_model` wholesale into ranking, boundary or compression fields.

When writing concrete facts such as distance, finish, surface or running style, verify them against the Reader already open for that race. This is a transcription/fact check only: do not reopen candidate selection or perform a second evidence scan.

Repeated wording is acceptable when the underlying judgment is genuinely similar. Generic prose is not a reason to change marks.

Older FROZEN outputs remain immutable.

## 3. Save each venue

Place one full venue Decision Core array at:

```text
<output-root>/v053/incoming/<venue>.json
```

Then:

```bash
python horse-racing/jrdb/src/racenote_v053_single_day.py save \
  --root <output-root>/v053 \
  --decisions <output-root>/v053/incoming/<venue>.json
```

Save is immutable per venue. A second materially different write must not
silently replace an authored venue.

For r2 sessions, `save` applies the rebuilt boundary guard before writing the
authored venue. A failed boundary identity is an authoring error and must be
fixed before Freeze; it is not deferred to post-race review.

## 4. Freeze the day

After all expected venues have been saved:

```bash
python horse-racing/jrdb/src/racenote_v053_single_day.py freeze \
  --root <output-root>/v053
```

Required status:

`FROZEN_CLEAN_BLIND`

Freeze produces:

```text
v053/frozen/
  records.json
  day_handoff.json
```

No A/B barrier is required.

## 5. Verify before publication or settlement

```bash
python horse-racing/jrdb/src/racenote_v053_single_day.py verify \
  --root <output-root>/v053
```

Verification re-checks:

- sealed forecast_prep identity;
- Reader hashes;
- race/horse roster;
- all authored Decision Core hashes;
- v0.5.3 Decision Core validation;
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
- `RACENOTE_CLEAN_BLIND_V051_V053_AB_RUNBOOK_v0_1.md`

They are not required for normal v0.5.3 operation.

## 7. Operational principle

The promoted baseline remains v0.5.2. v0.5.3 r2 is the current boundary-safety candidate.

The mental model is:

```text
PACI / Historical Warehouse
  -> one clean Reader
  -> v0.5.2-style ordinary five + win-first roles
  -> one external asymmetric challenger
  -> one fixed-boundary KEEP/ADMIT decision
  -> immutable Freeze
```

Do not optimize candidate-set diversity after the ordinary five is formed.

Do not treat BTDAY-0077 or BTDAY-0078 as r2 performance samples. They are
pre-rebuild audit artifacts and are closed unprocessed in the research ledger.

A/B machinery should be introduced only when there are actually two competing
forecast contracts to compare.

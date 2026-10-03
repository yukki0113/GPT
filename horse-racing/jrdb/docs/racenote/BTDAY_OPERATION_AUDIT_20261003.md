# BTDAY operational path audit — 2026-10-03

Status: completed audit and targeted fixes. Canonical procedure:
[`BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md`](BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md).

## Scope and observed failure

BTDAY-0042 and BTDAY-0043 were already selected in the persistent pool.
The PACI ZIPs were obtained from the existing Drive PACI folder. Both DAY PREPs
and clean input bindings passed with 36 races each. The prior work nevertheless
stopped during model judgment: BTDAY-0042 had incomplete mainline/Coverage
authoring in some race records, and BTDAY-0043 had no complete authored card.
Neither is a valid Freeze or cohort observation.

This was not an absent PACI, an unavailable Actions runner, or a proven defect
in the v0.4.4 horse-selection policy. It exposed missing operational gates and
unsafe temporary packaging.

## Inventory

| Boundary | Canonical asset | Audit finding and disposition |
| --- | --- | --- |
| Select unused day | `src/racenote_backtest_day_picker.py`, `config/racenote_backtest_day_pool_2026.json` | Present. The picker default is two days; current prospective runbook now explicitly uses `-n 1`. Inspect history before every draw; 0042/0043 must be resumed, not redrawn. Persist the state mutation on main. |
| Acquire PACI | `docs/JRDB_2026_Raw_Drive_Reference.md`, native Drive connector | Present external source and known naming/folder. Verify date, filename, ZIP/families. Existing Drive PACI makes this a direct transport step; upstream authenticated acquisition is only a missing/invalid asset fallback. |
| Build RaceNote | `src/build_racenote_daily.py`, `RACENOTE_DAILY_BUILD_v0_1.md` | Present full-day builder. Analysis canonical and RRDB v0.3 must be resolved; common data-storage runtime handles Parquet/DuckDB. Build manifest/validation PASS and as-of guards are required. |
| Bind judgment input | `src/racenote_prepare_forecast_input.py` | Present hash-bound clean Reader. Lossless DAY PREP Reader can retain market. The daily-build document now distinguishes it from the forecast input. Only the clean Reader and handoff enter judgment. |
| Author v0.4.4 | model + `FORECAST_HUMAN_CONTEXT_READER_v0_4_4_CANDIDATE.md` | The only semantic judgment step. Four mainline cases, independent ▲, RRDB interpretation, Coverage scan and provisional △2 comparison, marks and prose must be authored per race. Do not fill missing reasoning by script. |
| Bind authoring | new `src/racenote_bind_authored_v044.py` | Replaces ad hoc schema boilerplate: attaches only clean Reader horse identities/source hashes and fixed metadata. Requires complete model-authored compact decisions for exactly the Reader race set. Fails before writing if a case/decision is missing or Validator fails. |
| Preflight / Freeze | `src/racenote_freeze_prepared_forecast.py`, `src/validate_racenote_forecast_human_context.py` | Freeze now offers `--preflight-only`; regular Freeze runs the same full Validator before creating files. It also verifies Coverage count, shortlist/horse identities and four mainline cases for v0.4.4. The post-Freeze Validator remains mandatory. |
| Stage Git archive | new `src/racenote_stage_btday_archive.py` | Stages the established BTDAY tree only after source/Reader hash, race set, semantic hash and Validator checks. It copies safe handoffs, audits and Frozen records, and formats existing prose. Commit/readback to main uses an available direct GitHub path. |
| User output | `src/render_racenote_forecast_html.py` | Renderer now reads `reader_facing_reason` from Frozen v0.4.4 records. It previously rendered an empty comment when `axis_comment` was absent. |

## Removed unsafe path

The temporary `_tmp_btday044_freeze.py` script and its hardcoded
`btday-v044-freeze` workflow job were removed from main. That script derived
Coverage verdicts/comparison labels, mainline cases, ▲ case and RRDB review
text from marks, yet labelled those fields model-authored. It could produce
apparently valid but unreviewed traces. The canonical binder requires the
model's exact authored content and never supplies those judgments.

## Execution classification

Ordinary prospective BTDAY with existing Drive PACI:

1. **A Read/Audit:** latest main, pool/history, Drive identity and contracts.
2. **C Pure deterministic:** day build, clean binding, authored-record binding,
   preflight, Freeze, Validator, archive staging.
3. **B Git change:** save staged UTF-8 assets to main and read back hashes.

Actions is needed only for a separately established Actions-native requirement,
such as an authenticated upstream fetch when Drive PACI is missing or invalid.
Its availability is not a prerequisite for a normal BTDAY.

## Focused verification

- The preflight passed an existing 24-race clean-bound card and rejected a
  deliberately incomplete mainline before creating a Freeze directory.
- v0.4.4 binding checks passed a complete synthetic 24-race compact fixture and
  rejected a two-case race without producing a prepared file.
- A synthetic v0.4.4 24-race Frozen fixture passed archive staging with Reader
  hashes, semantic hashes and Validator PASS. The fixture was local smoke data,
  not a new forecast or cohort member.
- The Frozen HTML renderer displayed the authored `reader_facing_reason`.
- Source, procedure and removed workflow were read back from main after writes.

## Continuing BTDAY-0042/0043

Pool selections remain 2026-03-21 and 2026-02-14 respectively; both had
36-race DAY PREP and clean binding PASS in the interrupted work. Complete the
missing model judgments from each original clean Reader, run strict binding and
preflight for the full card, then Freeze, Validator and Git staging/readback.
Do not treat the selection or partial marks as a completed forecast. Do not
open target results or target-day market in the forecast work.

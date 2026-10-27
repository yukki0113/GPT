# RaceNote v0.5.5 r6 — BTDAY Pseudo-Batch Controller v0.1

Status: implementation / human-in-the-loop pseudo-batch. This controller is a
**deterministic coordinator**, not an autonomous prediction worker.

## Scope and non-negotiable boundary

This preserves the current
`RaceNote-Human-Context-Reader-0.5.5-candidate` /
`v055-prediction-freeze-confidence-review-r6` contract.

- Canonical picker reserves **one new BTDAY** at a time (never substitute a
  hand-selected date). T1 uses the existing accepted Historical Warehouse / PACI,
  RRDB, Course Fit and RaceLap procedure.
- Each sealed Lean Reader is independently reviewed by the LLM, race by race.
  No automatic scoring, ordinary-five selection, marks, Confidence grades or
  prediction prose are introduced.
- Prediction Freeze **must already be committed** before the separate LLM
  Confidence review. Canonical r6 workflows remain unchanged.
- Only after `TURN2_COMPLETE` and both clean-blind handoffs are committed does
  this controller count a BTDAY. Partial T1/T2 never enters progress.
- **No result, payout, final popularity or target-market input** is opened by
  the controller. Keep all results unopened until the full batch cohort is
  sealed. The subsequent result unlock/evaluation remains a separate T3 step.
- It runs synchronously per operation. A single chat request can direct an
  assistant to work through multiple days using checkpoints, **but there is
  no unattended background LLM inference or completion notification**.
  GitHub Actions automatically reconciles progress when committed T2 summaries
  appear; it cannot author predictions.

## Stop conditions

| Mode | Meaning | Required arguments |
|---|---|---|
| `btday_count` | Finish exactly N fully frozen BTDAYs | `--target-btday-count 2` |
| `confidence_count` | Accumulate at least N of grade A/B/C | `--target-confidence A --target-count 100` |
| `either` | Grade target reached, **or** day safety limit reached | `--target-confidence A --target-count 100 --max-btday-count 15` |

**Every BTDAY is atomic for inclusion.** If the previous total is A96 and
the next whole day contributes A9, the frozen cohort contains **A105**.
There is no cut-off by venue, race number, or order.

`Z` remains the mandatory confidence for special races (debut/jumps), but
is not a `confidence_count` target in v0.1. It is still counted in progress.
The A cohort is emitted at seal time for every stop mode.

## CLI (from repository root)

```bash
SCRIPT=horse-racing/jrdb/src/racenote_v055_batch_controller.py

# Collect at least 100 confidence-A races
python "$SCRIPT" init --batch-id V055-BATCH-A100-001 \
  --start-selection-id BTDAY-0136 \
  --mode confidence_count --target-confidence A --target-count 100

# Alternatively: just two days
python "$SCRIPT" init --batch-id V055-BATCH-2DAY-001 \
  --start-selection-id BTDAY-0136 \
  --mode btday_count --target-btday-count 2

# Or A100 with a 15-day safety limit
python "$SCRIPT" init --batch-id V055-BATCH-A100-CAP15 \
  --start-selection-id BTDAY-0136 \
  --mode either --target-confidence A --target-count 100 \
  --max-btday-count 15

python "$SCRIPT" status --batch-id V055-BATCH-A100-001
python "$SCRIPT" sync --batch-id V055-BATCH-A100-001
python "$SCRIPT" seal --batch-id V055-BATCH-A100-001
```

Above examples are **alternatives**. v0.1 prohibits concurrent active batches
to avoid overlapping / ambiguous BTDAY ownership. Batch IDs and configuration
are immutable after creation; use a new batch ID for a new experiment.

If operating from GitHub, dispatch
`.github/workflows/racenote_v055_batch_controller.yml` on `main` with
`init` / `status` / `sync` / `seal` and the corresponding inputs.
A committed `v055/turn2_summary.json` on main automatically invokes
`sync-active`. The action commits changes **only inside**
`horse-racing/jrdb/backtests/batches/`.

## Operator loop / next_action

```text
status or sync → next_action

PICK          → reserve this exact next BTDAY by the canonical picker
T1            → execute T1 for its canonical selected date
T2_PREDICTION → LLM reviews every horse/race and commits llm_decisions.json
                → canonical Prediction Freeze
T2_CONFIDENCE → LLM reviews frozen ◎ and commits llm_confidence.json
                → canonical Confidence Freeze
T2_VERIFY     → finish canonical T2 summary, then re-run sync
SEAL          → execute 'seal' (no result access)
COMPLETE      → immutable clean-blind cohort available
```

`status` scans completed artifacts but does not commit state; `sync` records
verified completions and checkpoints. Both re-check the full prefix of completed
BTDAYs: a modified SHA, frozen mark, coverage or count **fails closed**. Repeated
`sync` is idempotent. If a run is interrupted, resume from `next_action`;
do not rerun an already frozen Prediction/Confidence.

A batch progresses on sequential BTDAY IDs (`0136 → 0137 → ...`), never skipping
a missing or incomplete ID. A missing selection is **PICK**, not an invented date.

## Sealed outputs

```text
horse-racing/jrdb/backtests/batches/<batch_id>/
  batch_manifest.json          # state, stop condition, cumulative grades, sessions
  completed_btday.json         # frozen verified BTDAY snapshot list
  confidence_A_cohort.json     # all A race identities + honmei + dual SHA bindings
  cohort_seal.json             # immutable cohort SHA and complete member manifest
```

Final status: `BATCH_COHORT_FROZEN_CLEAN_BLIND`. Each member binds
`selection_id`, `target_date`, `session_id`, `venue`, `race_no`,
`honmei`, `prediction_records_sha256` and `confidence_records_sha256`.

Before sealing, the controller verifies each canonical selection is a single
day, the T1 handoff, both committed frozen record blobs and handoffs, the
quality report seal, race/honmei coverage, confidence counts, and clean-blind
flags. The seal itself is rechecked on later status calls.

The seal makes the **pre-result A cohort** auditable. It does not certify
prediction correctness or profitability; those belong to a separate,
post-seal evaluation with an explicitly approved result unlock.

## Operational limits

- The controller does not itself fire the canonical picker, materialize T1
  assets, call an LLM API, or dispatch r6 prediction authoring. An assistant
  or operator advances those phases in the existing workflow.
- GitHub Actions sync events update checkpoints automatically; they do not
  schedule future user conversations or provide autonomous notifications.
- The currently running ChatGPT turn has finite execution time/context.
  For longer batches, hand off to the next chat/turn using the committed
  manifest and `next_action`, with no duplicate prediction.
- Only one active batch is allowed in this first version.
- All operations must run on a workspace with the complete committed
  canonical BTDAY files; the workflow uses `main` as that workspace.

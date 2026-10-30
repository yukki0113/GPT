> **2026-10-30 現行r6補足**：新規2025 Historical BTDAYのT1入口は `.github/workflows/racenote_v055_r6_t1_orchestrator.yml` の `NEXT` / `EXISTING` / `STATUS` / `T2_ONLY`。通常のT2は冒頭で次T1を先行起動し、二段階Freeze後に次T1の終了・ZIP Artifactを確認する。詳細は [現行PIPELINE手順](RACENOTE_V055_R6_PIPELINE_CURRENT_RUNBOOK_20261030.md) を優先。旧版の手動起動・統合Freeze・forward専用説明は、その対象に限る。原文バックアップ：`operation-backups/20261030_pre_pipeline/RACENOTE_V055_R6_SHARED_T1_v0_1.md`。

# RaceNote v0.5.5 r6 — shared historical BTDAY Turn1

Scope: BTDAY-0138 and later, **2025 historical warehouse dates** in the
current golden data generation. Other years and PACI require a separately
validated input materializer; the shared route **fails closed**.

## Entry point

`.github/workflows/racenote_v055_r6_btday_turn1_shared.yml`

After a canonical `BTDAY-NNNN/selection.json` has been committed, create
**one** request file in **one commit**:

`horse-racing/jrdb/backtests/requests/BTDAY-NNNN.v055r6-turn1`

The shared workflow resolves the exact changed request file and reads
the existing canonical selection; the BTDAY number/date are not hardcoded.
The request's date must be a single 2025 historical-warehouse date.
BTDAY-0137 and earlier are intentionally excluded because their original
workflows are historical operations. Do not create temporary per-BTDAY T1
workflows for 0138+.

## RRDB weekly CURRENT transport

The shared entry point invokes the single maintained script:
`horse-racing/jrdb/src/racenote_fetch_rrdb_current.py`.

- Downloads the same canonical Drive **file ID** each run, not a stale
  `expected_size` / SHA from a prior week.
- Performs file-size bounds, ZIP CRC, safe ZIP-member checks, presence of
  `postrace_review/v0_1/current.json`, and JSON object check.
- Produces a receipt with the exact downloaded content SHA-256, byte size
  and file ID. T1 stores it at
  `<BTDAY>/<YYYYMMDD>/source_audit/rrdb_current_receipt.json`.
- The full T1 read/bind remains clean blind; neither results nor target
  market are opened.
- A valid-looking ZIP alone is **not** a semantic validation of RRDB
  coverage/content; canonical enrichment/Reader/quality gates still apply.

Do not update the RRDB SHA to the current file by merely changing the
old static manifest. Do not reuse this per-run mutable transport for
immutable historical inputs, Prediction Freeze, or Confidence Freeze.

## Retry and reproducibility

On an external download failure, fix the transport and retrigger the
same request (provided no immutable T1 was committed). After a successful
T1, both the immutable Reader/session and RRDB receipt form the evidence
for that BTDAY. Later updates of RRDB CURRENT **must not** alter the
existing BTDAY T1/Prediction/Confidence Freeze.

Each triggering push should modify only one new request path. Mixed
multi-request commits deliberately fail closed.

## Remaining boundaries

The 2025 BAC/KYI raw archive names and pinned Course Fit/RaceLap evidence
are inherited from the currently accepted historical T1 baseline.
This workflow does not claim all years, daily PACI forward days, or changing
Course Fit/RaceLap generation are automatically supported.

T2 continues through the existing r6 two-phase LLM authoring and separate
canonical freezes. The Batch Controller consumes completed T2, not guesses.

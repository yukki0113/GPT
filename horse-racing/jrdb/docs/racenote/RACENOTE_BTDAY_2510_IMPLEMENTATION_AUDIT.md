# BTDAY source routing implementation audit — Issue #2510

Status: **DRAFT / NOT ACCEPTED FOR PRODUCTION NEXT**

## Implemented candidate components

- `racenote_v056_btday_source_router.py` resolves one source per date, preserves
  explicit exclusions, requires an independently verified pinned receipt, and
  creates a non-mutating repeat-draw proposal. The proposal is not an atomic
  reservation and is not connected to production NEXT.
- `racenote_v056_t1_orchestrator.py SHADOW` reads a separate inventory and
  previews a proposal without updating the pool, Selection, T1, or Freeze.
- `racenote_v056_btday_paci_preflight.py` validates the PACI source receipt,
  SHA, ZIP CRC and BAC/KYI race and horse rosters using the common JRDB parser.
- `racenote_v056_btday_paci_t1.py` is an unactivated candidate adapter using
  the shared PACI T1 materialization. It checks Selection and source identity,
  actual Analysis/RRDB/RaceLap as-of evidence, and extracted RRDB bytes.
  FORWARD retains its own canonical root, ID and preflight.
- `.github/workflows/racenote_v056_btday_paci_shadow.yml` is a manual,
  isolated staged-artifact test. It reads a GitHub Artifact by ID, checks its
  pinned archive SHA, builds in `/tmp`, and produces a clean Reader ZIP; it
  cannot reserve a selection, modify main, or run Prediction/Confidence.

The staged ZIP must include `inputs/source_row.json`, a pinned accepted
receipt at the relative path declared in that row, `inputs/PACIyyMMdd.zip`,
`inputs/paci_receipt.json`, `inputs/analysis/`, `inputs/course_fit/`,
`inputs/rrdb/`, `inputs/rrdb.zip`, `inputs/rrdb_receipt.json`,
`inputs/racelap/`, and
`horse-racing/jrdb/backtests/BTDAY-NNNN/selection.json`. The Selection must
be a v2 shadow selection whose date, source generation and receipt SHA match
the row. All paths are extracted into a fresh runner sandbox. The artifact SHA
and ID are explicit workflow inputs; no authenticated Drive access is used.

## Evidence available

- The existing main `BTDAY-0181`, 2025-05-25, records Warehouse generation
  `jrdb_normalized_warehouse_v1_2010_2025_g20260921`, 36 Reader races and
  `market_blind=true`, `result_opened=false`, `target_market_opened=false`.
  This is an existing baseline readback, not acceptance of the new adapter.
- The 2026-11-07 PACI from the canonical Drive folder passed local source
  preflight: SHA-256 `61ffacbb935ee5064ba84080e7c6921c080879b43b9bed9153d6cc27a4d81057`,
  36 races and 501 horses. This is not a BTDAY T1 acceptance.
- Existing FORWARD handoff for 2026-11-07 records 36 Reader races, the same
  PACI SHA, and Analysis/RRDB coverage through 2026-11-01. It is an existing
  forward baseline and does not establish BTDAY adapter acceptance.
- Actions run `42770061388` passed the v0.5.6 contract tests after fixing
  unittest discovery. Local fixture tests cover source resolution, replay,
  SHA mismatch, receipt tampering, as-of rejection, and FORWARD compatibility.

## Remaining before production activation

- Validate real readiness receipts and atomic reservation/retry behavior;
  integrate v2 draws with NEXT/EXISTING/STATUS/T2_ONLY and shared T1 workflow.
- Run the candidate PACI BTDAY shadow workflow with accepted, pinned, date-specific
  Analysis/RRDB/RaceLap and Course Fit artifacts; verify T1 Artifact, main
  readback and the existing Prediction/Confidence Freeze boundaries.
- The 2026-11-07 PACI and the 2026-11-01 RRDB snapshot are private Drive
  files. Actions must not use authenticated Drive or raw `gdown`. An approved
  public read-only pinned transport or pre-staged GitHub Artifact is needed;
  do not change file sharing or label them READY based on this audit.
- Execute new 2025 Warehouse and 2026 PACI BTDAY E2E runs and confirm source
  receipts, Reader counts and blind state. Keep the existing 181 selections
  and all existing T1/Prediction/Confidence Freezes immutable.
- Activate mixed-source NEXT only after both sources and replay/idempotency
  gates pass. No years or unverified PACI dates are enabled by this draft.

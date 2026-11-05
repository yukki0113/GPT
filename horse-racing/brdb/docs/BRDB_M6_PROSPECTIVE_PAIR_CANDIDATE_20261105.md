# BRDB M6 — prospective paired model candidate (2026-11-05)

**Status: engineering handoff only. M6 is NOT COMPLETE. Neither prospective evidence nor an independently attested historical pre-race pedigree source has been acquired.**

## Why this exists

PR #2408 executed a conditional retrospective 2021–2025 five-fold comparison. The fixed non-blood baseline and sire/BMS-line challenger were research-only, fit after the fact. Existing RaceNote v0.5.6 Prediction/Confidence Freeze stores marks, not calibrated horse-specific win probabilities. Therefore P1-7's originally required **two pre-race frozen p(win) series for the identical horses** still has **zero accepted real pairs**.

The module `src/run_brdb_m6_prospective_pair_candidate.py` supplies the missing **model-generation candidate**, not the independent attestation.

## Inputs and permitted source

1. Explicit SHA-pinned, **private** 2016–2025 historical result mart (`--mart`) and dated UKC/KYI reconstruction (`--history`), as accepted in `BRDB_M6_CONDITIONAL_RETROSPECTIVE_20261104.md`. Those source ZIPs/rows are not committed to Git.
2. Explicit SHA-pinned, **private** future target CSV (`--target`) produced by the existing JRDB PACI/UKC reader path. BRDB does not reimplement fixed-width parsing. Columns: `target_date` (YYYY-MM-DD), `venue`, `race_no`, `race_key`, `horse_no`, `horse_id`, `venue_code`, `surface_code`, `distance_m`, `race_class_code`, `sire_line_code`, `broodmare_sire_line_code`, `ukc_data_date` (YYYYMMDD). An audited upstream feed must vouch for each race and horse ID; this module does not.
3. Existing **RaceNote-owned** `v056/frozen/{records.json,day_handoff.json}` (`--v056-root`). BRDB reads it and calls the already implemented `audit_brdb_m6_v056_freeze_evidence.check`; BRDB does not alter a RaceNote Freeze.

## Model

- Train on 2016–2025 only, reusing the accepted M6 retrospective cohort, model function, and fixed feature sets. This is **not** a copy of RaceNote's forecasting model.
- Independent binary logistic baseline: venue, surface, distance 200m band, class, horse number, month.
- Blood challenger: same plus sire-line and BMS-line codes.
- Normalize each model's predicted weights within each race to meet the existing `brdb-p1-7-pre-race-pairs-v0.1` contract. This is a **new per-race normalization of the historical binary research model**, not evidence of probability calibration. Do not silently compare its metrics to the unnormalized historical binary log loss.
- Reject target result/market columns, unknown canonical horse ID, future-dated UKC observation, SHA changes, incomplete/duplicate frozen roster and out-of-training targets.

## Command (run *before races* with genuine private inputs)

```bash
python horse-racing/brdb/src/run_brdb_m6_prospective_pair_candidate.py \
  --mart <PRIVATE_MART_PARQUET> --mart-sha <ACTUAL_SHA256> \
  --history <PRIVATE_HISTORY_CSV_GZ> --history-sha <ACTUAL_SHA256> \
  --target <PRE_RACE_TARGET_CSV> --target-sha <ACTUAL_SHA256> \
  --v056-root <RACENOTE_V056_DAY_ROOT> \
  --out <PRIVATE_RESEARCH_OUTPUT_DIR>
```

Outputs: `PRIVATE_prospective_pair_candidate.json` (licensed horse-level record, **private only**) and `prospective_pair_candidate_audit.json` (non-identifying hashes/counts). The paired JSON always has `prediction_safe=false` and the audit always has `p1_7_log_loss_evaluable=false`.

## External freeze gate — not implemented by this module

**Before the first race's start** an independent reviewer must confirm that the *unchanged* model candidate and all input features were obtainable beforehand, and that the immutable GitHub/Drive receipt containing the model and pair SHA was committed before the race; this must be checked against actual provider/commit metadata, never a timestamp field supplied by the caller. The private licensed pairs must **not** be uploaded to GitHub simply to produce a commit; a lawful private immutable storage receipt plus public SHA-only manifest may be considered after separate approval.

A historic 2016–2025 ZIP member date and user-reported provider equivalence are not independently attested original distribution bytes. A SHA-pinned future paired candidate is not a true forward study until all external as-of checks pass and later results are scored using prespecified paired, dependent uncertainty.

## Acceptance boundary

No BRDB CURRENT, PWA, Newspaper, RaceNote, betting workflow, Blood Score or existing Freeze mutation. Keep Issue #2395 open; M6 scientific completion still requires source attestation, prospective paired probabilities, outcomes, paired cluster inference, and final acceptance. Synthetic local unit tests cover target roster/missingness/date and per-race probabilities. **Real JRDB source replay and actual pre-race Freeze are not claimed.**

## 2026-11-05 readiness and next owner

- The user reports that **JRDB support explicitly advised treating archived distributions as equivalent**. Record this as `PROVIDER_SUPPORT_EQUIVALENCE_REPORTED_BY_USER`. Retrospective 2016–2025 modeling may proceed under this accepted provider-support premise without repeatedly reopening the same question; independent original-byte release timestamp and a real future prediction Freeze remain distinct claims.
- Private licensed datasets and horse-level predictions must not go to the existing Google Drive `blood_review` folder (it has `anyone:reader`). A separately created **non-shared owner-only** folder `BRDB_M6_PRIVATE_RESEARCH` was verified on 2026-11-05. Its current identity and read/write rights must be verified again before any licensed data upload.
- The canonical PACI folder has no `PACI261107.zip` as of the 2026-11-05 check; the matching RaceNote v0.5.6 `frozen/day_handoff.json` was also not present on main. Do not manufacture a prospective run.
- Draft PR #2410's pull-request CI, [run 41940017843](https://github.com/yukki0113/GPT/actions/runs/41940017843), completed successfully: **11 focused synthetic tests passed** (6 candidate + 5 Freeze-gate).
- Full cross-project adapter, private input materialization, external freeze receipt, and official SED scoring are separately owned by [Issue #2411](https://github.com/yukki0113/GPT/issues/2411), with explicit Codex/Work handoff. This candidate module is not a scheduled production forecast.

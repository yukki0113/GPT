# JRDB Daily ZIP HTTP 403 investigation — 2026-09-12

Status: **IN PROGRESS**

This record tracks the 2026 Training Edge v0.2 OOT acquisition failure observed in Issue #857 / Actions run 34565399143.

Observed failing daily URLs:
- `SED260219.zip` -> HTTP 403
- `UKC260219.zip` -> HTTP 403
- `BAC260220.zip` -> HTTP 403

The frozen Training Edge v0.2 evaluator was not reached. No 2026 OOT model result was observed.

Known controls from the same failed run:
- 2026-02-19 BAC/KYI/CHA/CYB returned 404 (NOT_FOUND)
- 2026-02-20 KYI/SED/UKC/CHA/CYB returned 404 (NOT_FOUND)
- 2026-02-21 all six required kinds downloaded successfully
- 2026-02-22 all six required kinds downloaded successfully

Next diagnostic step: authenticated targeted HTTP probes against the three 403 URLs plus known 200/404 controls. No Training Edge model or calibration changes are permitted during this investigation.

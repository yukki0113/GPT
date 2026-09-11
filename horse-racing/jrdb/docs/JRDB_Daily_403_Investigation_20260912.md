# JRDB Daily ZIP HTTP 403 investigation — 2026-09-12

Status: **RESOLVED AS TRANSIENT HTTP ANOMALY / SAFE RETRY REQUIRED**

## Scope

This record tracks the 2026 Training Edge v0.2 OOT acquisition failure observed in Issue #857 / Actions run `34565399143`.

The frozen Training Edge v0.2 evaluator was **not reached** in that run. No 2026 OOT model result was observed and no model feature, solver, calibration, or threshold was changed during this investigation.

## Initial failure

Three daily requests returned HTTP 403:

- `SED260219.zip` -> HTTP 403
- `UKC260219.zip` -> HTTP 403
- `BAC260220.zip` -> HTTP 403

The same run showed the surrounding requests behaving normally:

- 2026-02-19 BAC/KYI/CHA/CYB -> HTTP 404 (`NOT_FOUND`)
- 2026-02-20 KYI/SED/UKC/CHA/CYB -> HTTP 404 (`NOT_FOUND`)
- 2026-02-21 all six required kinds -> HTTP 200 / downloaded
- 2026-02-22 all six required kinds -> HTTP 200 / downloaded

Across the 2026-01-01..2026-09-06 scan, the fetch summary was:

- `DOWNLOADED`: 449
- `NOT_FOUND`: 1,042
- `ERROR`: 3

The three 403 responses were sparse and interleaved with ordinary 404 responses. Acquisition continued normally afterward. This is inconsistent with a persistent credential rejection or sustained global rate limit.

## Authenticated targeted probe

Issue #870 executed a targeted authenticated probe against the three problem URLs plus known 404 and 200 controls. Each URL was requested three times.

Observed after the original failure:

- `SED260219.zip` -> 404 x3
- `UKC260219.zip` -> 404 x3
- `BAC260220.zip` -> 404 x3
- known 404 control `BAC260219.zip` -> 404 x3
- known 404 control `KYI260220.zip` -> 404 x3
- known 200 control `BAC260221.zip` -> 200 x3
- known 200 control `SED260221.zip` -> 200 x3

The 404 responses used `Content-Type: text/html` and server `Google Frontend`; the 200 controls returned `application/x-zip-compressed`. No `WWW-Authenticate` response was observed on the controls.

## Conclusion

The three original HTTP 403 responses were **transient**. They are not permanently forbidden JRDB objects and must not be reclassified directly as `NOT_FOUND`.

The evidence supports a short-lived upstream/JRDB/Google Frontend HTTP anomaly. The exact internal upstream mechanism cannot be established from the available client-side evidence, so the investigation does **not** claim a specific WAF or rate-limit cause.

The correct safe behavior is:

1. HTTP 404 -> immediate `NOT_FOUND` as before.
2. HTTP 401 -> hard credential failure as before.
3. HTTP 403 -> retry with the existing bounded exponential-backoff policy.
4. 403 -> retry -> 404 => `NOT_FOUND`.
5. 403 -> retry -> 200 => validate ZIP and download normally.
6. Persistent 403 through the retry budget => hard `FetchError`; never silently skip it.

## Remediation implementation

A separate acquisition entrypoint was added so the model freeze is not modified:

- `horse-racing/jrdb/src/fetch_jrdb_history_retry403.py`

It imports the canonical fetcher and adds only HTTP 403 to its retryable HTTP-code set.

Regression coverage was added at:

- `horse-racing/jrdb/tests/test_fetch_jrdb_history_retry403.py`

The test cases freeze the intended semantics:

- transient 403 -> 404 => `NOT_FOUND`
- transient 403 -> 200 => normal validated download
- persistent 403 => hard failure after the retry budget

## OOT integrity guard

The 2026 Training Edge v0.2 OOT rerun must keep model source SHA:

`b0865a25f743d2cda34928a6603266ce520c0ba9`

Only the acquisition entrypoint may differ. The acquisition-fix commit/SHA must be recorded separately in the rerun Evidence. Issue #857 remains an acquisition-failure record until a clean rerun is completed.

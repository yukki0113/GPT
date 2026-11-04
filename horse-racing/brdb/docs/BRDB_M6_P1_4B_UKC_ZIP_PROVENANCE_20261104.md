# BRDB M6 P1-4b — 2016–2025 historical UKC ZIP timestamp/provenance audit (2026-11-04)

## Result

**Immutable archive membership verification: PASS. Historical pre-race source-availability attestation: HOLD. Predictive eligibility: 0 (no independent distribution evidence).**

This is an extension of P1-4 gate ([BRDB_M6_P1_4_ASOF_GATE_20261104.md](BRDB_M6_P1_4_ASOF_GATE_20261104.md)); it does **not** change the frozen BRDB CURRENT, RaceNote, PWA, or predictions.

Using the native connected Google Drive reader, 10 accepted annual `UKC_2016.zip` through `UKC_2025.zip` were retrieved from the established canonical UKC inventory location. SHA-256 and size of each ZIP matched the source-pinned `config/public_drive/ukc_1999_2025_research_inputs_v0_1.json` manifest. Each ZIP was CRC-checked; 1,082 `UKCYYMMDD.txt` members were accepted. The year encoded in every member name was checked against the containing annual ZIP.

**ZIP member timestamps, relative to the nominal date embedded in each file name:**

| ZIP year | Members | 2+ days earlier | Previous day | Same day | Later |
|---|---:|---:|---:|---:|---:|
| 2016 | 107 | 0 | 103 | 3 | 1 |
| 2017 | 111 | 0 | 0 | 0 | 111 |
| 2018 | 109 | 0 | 100 | 8 | 1 |
| 2019 | 110 | 0 | 47 | 0 | 63 |
| 2020 | 109 | 0 | 2 | 1 | 106 |
| 2021 | 106 | 0 | 105 | 1 | 0 |
| 2022 | 108 | 0 | 107 | 1 | 0 |
| 2023 | 107 | 0 | 104 | 3 | 0 |
| 2024 | 106 | 0 | 103 | 2 | 1 |
| 2025 | 109 | 2 | 101 | 3 | 3 |
| **Total** | **1,082** | **2** | **772** | **22** | **286** |

Evidence of possible later repackaging: **all 111 members of `UKC_2017.zip` carry timestamps in 2019**, specifically August 4, 2019; several 2019 members also have August 4, 2019 times, while 2020 has many December 20, 2020 timestamps. These are **embedded ZIP metadata**, not independently authenticated creation or delivery events. The distribution origin and original bytes at each target race date remain unproven.

Google Drive reports `created_time` **2026-09-16** for all 10 annual UKC ZIP files. Drive `modified_time` and member `mtime` must not be promoted into pre-race source provenance. The ZIP member date in a filename is a *nominal target date*, not a verified distribution or race-start timestamp.

## Historical daily-source discovery

The established canonical JRDB Raw folder was inspected via native Drive folder listing; it exposes 2026 daily material and year-level historical SED archives. Searches for specific expected old names `PACI160105.zip`, `PACI170105.zip`, `PACI250105.zip` returned zero results. **These are SEARCH MISS observations, not proof that daily historical PACI records do not exist.** Neither a complete historical-PACI root inventory nor independent JRDB release-time log was obtained.

## Decision and remaining evidence

- **10/10 ZIP SHA+size and 1,082/1,082 member/date structural checks: PASS.** Archive CRC passes; synthetic negative/positive tests: 4/4 PASS in the private runtime.
- **Attribution to specific pre-race member bytes: NOT VERIFIED.** Even a previous-day ZIP member mtime is mutable and does not establish distribution time or content identity as delivered.
- **Predictive cohort eligibility: still 0**; do not reinterpret 772 previous-day members as 772 eligible observations or infer any horse-level safe numerator.
- Retain P1-5, P1-6, P1-7 predictive inference on HOLD. The accepted descriptive P1-3 remains valid in its narrower scope.
- Next evidence route: inventory historical daily PACI/UKC source directories and archived acquisition or release logs with immutable original ZIP/member SHA, provenance, and independently verifiable earliest availability. Only then design race/horse-level as-of crosswalk and audit; strictly exclude same-day when delivery time is unknown.
- Do not send licensed JRDB ZIP/member rows to public GitHub. This report includes aggregates only.

Local reproducibility artifacts: `audit_ukc_historical_zip_timestamps.py`, `test_audit_ukc_historical_zip_timestamps.py`, and private manifest of source SHAs/sizes/Drive metadata. Private aggregate JSON SHA-256 `e300bfa54efcf7631700b10d3f23b9cb0bd5fed6d62a2026a7e8caf0450ab132`. Exact input archive SHA values are in the already committed source-pinned UKC manifest.

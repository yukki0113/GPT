# JRDB DuckDB 2.0.1 Phase 1 qualification — 2026-11-23

Status: **candidate verified on JRDB historical Parquet; unmerged pending full Forecast Reader real-data E2E**.

## Scope

Prioritize central horse-racing JRDB / Forecast Reader. The shared data-storage pin changes from DuckDB 1.1.3 to 2.0.1 LTS. No changes to Forecast Reader S0–S4, eight-axis semantics, prediction rules, data, or canonical Parquet generation are included.

## CI evidence (upgrade PR #2713)

- Common data storage: Python 3.12 / 3.13 **PASS**; each 62 pytest tests plus existing downstream tests.
- Forecast Reader: Python 3.12 / 3.13 **PASS**; 120 tests each.
- JRDB common reader: **PASS**.
- Central horse-racing canonical CI: **PASS**.
- CI-exported open-source DuckDB 2.0.1 wheel, Python 3.12 and 3.13: SHA-256 audited; offline install in Python 3.13 **PASS**.
- Wheel (Linux x86-64 CPython abi3, glibc >= 2.27) SHA-256:
  `39ffeb136abed770a496e5592a464f18a07b1543e7ddb1ff6453215e179f1647`.
- CI logs: https://github.com/yukki0113/GPT/actions/runs/45103518912 and https://github.com/yukki0113/GPT/actions/runs/45103518921 .

## Immutable real JRDB dataset

- Official Drive source: Analysis CURRENT archive, obtained through connected native Drive.
- Historical **authority**: immutable 2026-10-18 generation `analysis-v1_4-postrace-20261018-01`, with manifest content SHA-256 `f8627085b9ff905166a8b6c51f842bdc382d2a3529b11fb72086d41b843f5557`.
- Extracted ten historical 2016–2025 Parquet assets were **individually verified** against this manifest by SHA-256 and size. Current archive's **2026** partition was excluded: no post-cutoff use.
- Verified 10 partitions, **481,627 horse starts**.
- Current archive itself SHA-256: `a98ddbc0def1894b40a1420f3e032f379dc32c33b6fb5bee74c98950a56ed232`. This current archive is a transport container, *not* evidence of the October as-of; the older immutable manifest binds each historical asset.

## Exact 1.1.3 vs 2.0.1 engine comparison (same source bytes)

Both official DuckDB wheels were installed into separate Python 3.13 virtual environments. Both executed the same read-only SQL against the verified Parquet files. Input view uses the repository's `read_parquet(..., hive_partitioning=true, union_by_name=true)` contract.

| Test | Scope | Outcome | Canonical result SHA-256 |
| --- | --- | --- | --- |
| Year / missing counts | 10 years | MATCH | `a1e2e5b292ac73fbbbc760704fcfcca1114ac50a2e3eef7d2245dacd8d0d3437` |
| Condition groups, wins / top-3 | 407 groups | MATCH | `14f2d2eca17bc671a17f799aedf2c19bc94d46ebcd33edfc671aa3f80c03451f` |
| Previous-race key joins | 10 yearly groups | MATCH | `f6a183de7e116c6a3adc81f53b440884d5fd656c359e8b473fca4cb89487daf4` |
| Sample attribute group query | 128 groups | MATCH | `4b702793559876d7ead2fd803acf173739720dc0d69753823d1b0feea7488871` |
| Forecast Reader historical SQL projection, sorted row stream | **481,627 complete projection rows** | **MATCH** | `607c14349a770f74be934020e17bbce2cb7aa49632e58b39f94b24013fb74fd6` |

The sample attribute SQL tested available historical attributes, **not the full canonical eight-axis Forecast Reader result**; previous distance/class were not reconstructed in the sample query. Durations are one-off diagnostics, not evidence of systematic speed improvement.

## Canonical real-race full E2E parity — 2026-10-25 Kyoto 11R 菊花賞

**Both engine versions executed the exact same repository Forecast Reader CLI end to end**, in isolated Python 3.13 environments. Official native Google Drive was used to obtain all inputs, without publishing raw JRDB bytes.

Immutable source material, SHA verified individually before use:

- PACI261025.zip: SHA `2fcce9418b51b55de3d6ea70e1c73510c24a9daf40047d0d1d6a026ea8847484`, 500,673 bytes.
- Analysis generation manifest `analysis-v1_4-postrace-20261018-01`: SHA `f8627085b9ff905166a8b6c51f842bdc382d2a3529b11fb72086d41b843f5557`; prior-year 2016–2025 Parquet assets 10/10 verified.
- Warehouse final manifest `jrdb_normalized_warehouse_v1_2010_2025_g20260921`: SHA `62fb6eb79546e3e0dd2b70592e0324d52c33c361f7073e78c2b420b82e1e008d`; BAC 2015–2025 11/11 and SED2025 1/1 verified by SHA and size.
- Source native Drive metadata was checked twice for stable identity, original name, parent, size, and modified time. Previous historical as-of provenance is based on the immutable manifest publication times, **not on a claim that this comparison was observed in October**.

The same request `2026-10-25 / 京都11R / as_of=2026-10-25T15:30:00+09:00`, source paths, and metadata observations were passed to both environments; identical Forecast Reader source/config was used.

| E2E dimension | 1.1.3 and 2.0.1 |
| --- | --- |
| Historical rows | 481,627; exact parity |
| Historical race count | 34,548 |
| S0 exact race keys | 8, identical keys |
| S1–S4 supplements | 0; same pre-existing shortage |
| Cohort horse starts | 143 |
| Previous join | 143 requested / 143 joined / 0 missing |
| PACI runner previous joins | 18/18 |
| Eight-axis trends | Every axis 143 valid / 0 missing in exact-only cohort |
| Target results accessed | No, `as_of` guard respected |
| Technical reader status | **PARTIAL in both versions**, not PASS |
| Status reason | `NO_ACCEPTABLE_SUPPLEMENT`: 8/10 selected races, no permissible extra |
| Whole evidence bundle | **All four JSON outputs byte-identical between engines** |

Both versions produced these same file SHA-256s:

- `forecast_evidence.json`: `1e7e9f6c6d5e31971d28ccc9f1cb83e7170c48a2fbf3624412eb666286eaf861`
- `sampling_audit.json`: `3f39eda328c7ecc80480c6584a7c7fe00a383e89e3aa8c8984f728e06d3f1dd9`
- `source_audit.json`: `955747262bf9d6067cd98c6184c927b3f45890578b20bd6e11eda8a4c373f292`
- `manifest.json`: `aa2bbad364553f8c46db76fb1cd99e1d5bfc87b248afe0224c7049ff745`

**Important distinction:** the original October acceptance report documented Reader PASS with eight selected races under its then-code/config SHA. Under the *current same-code* comparison, both 1.1.3 and 2.0.1 yield PARTIAL because selection marks no acceptable supplement as a sampling flag. This difference from the older acceptance is **not caused by the DuckDB version**. Do not relabel PARTIAL as PASS or change scientific semantics within this dependency upgrade. Investigate the prior acceptance vs current sampling gate separately.

## Deployment safeguard

Previously `data_storage check-deps` checked only that DuckDB was importable. The proposed upgrade now rejects stale 1.1.3 as `DEPENDENCY_MISMATCH` when 2.0.1 is the canonical pin, preventing legacy local virtualenvs from silently bypassing the upgrade. Focused tests cover both mismatch and expected-version success. Existing deployments must run the normal documented requirements repair path after merging.

## Outstanding before production promotion

- [x] 2.0.1 CI test runs (Python 3.12/3.13) and common reader tests.
- [x] Actual JRDB immutable history source SHA/size validation; same-source DuckDB result parity.
- [x] Validated, offline-installable DuckDB 2.0.1 wheel from Actions CI.
- [x] Full historical PACI / BAC+SED / previous-run Forecast Reader E2E on same fixed pre-race case: S0–S4, eight axes, 4/4 evidence bundle bytes identical across 1.1.3/2.0.1. Technical status PARTIAL in both; no semantic regression from engine.
- [ ] Validate other mandatory shared-consumer smoke contracts affected by the global pin and the rollout/rollback plan, then merge the reviewed candidate.

**The full Reader E2E parity is complete, but its technical result remains PARTIAL in both versions.** Do not claim scientific PASS or silently alter sampling semantics. Source data and existing Actions remain unchanged during the dependency promotion.

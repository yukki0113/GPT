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

## Outstanding before production promotion

- [x] 2.0.1 CI test runs (Python 3.12/3.13) and common reader tests.
- [x] Actual JRDB immutable history source SHA/size validation; same-source DuckDB result parity.
- [x] Validated, offline-installable DuckDB 2.0.1 wheel from Actions CI.
- [ ] Full historical, PACI, BAC/SED Warehouse-condition and previous-run Forecast Reader E2E on a pinned pre-race case under DuckDB 2.0.1; assert S0–S4, eight-axis output and evidence bundle parity with established 1.1.3 baseline.
- [ ] Validate other mandatory shared-consumer smoke contracts affected by the global pin and the rollout/rollback plan, then merge the reviewed candidate.

**Never interpret the partial real-data parity above as a completed full Forecast Reader acceptance.** Data and existing Actions remain unchanged until promotion.

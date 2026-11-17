# BRDB D4 — PACI real-field input gate and E2E acceptance

Date: 2026-11-16/17  
Status: **PASS — REAL PACI FULL-FIELD RESEARCH E2E ACCEPTED / NO PREDICTION AUTHORIZATION**

This remains research-only. No deployment, score, forecast, BRDB CURRENT mutation, frozen Blood Review mutation, RaceNote/PWA/Newspaper publication, or prediction-safe promotion is authorized.

## 1. Source contract

- PACI source: canonical JRDB Drive Raw/PACI folder through the established Drive/Data Storage route.
- Parser: `horse-racing/jrdb/src/jrdb_raw.py` `Parser`, `canonical_members`, `split_fixed_records`.
- Race identity: one exact BAC race key, complete KYI declaration field, exact UKC join by canonical 8-digit `horse_id`.
- BAC supplies date, venue, surface and distance. It does **not** establish official going; `track_condition_code` is omitted.
- No odds, result, score, rank, probability or prediction is accepted.
- D3 inputs are the exact frozen three-file research outputs and remain `AS_OF_UNVERIFIED`.

## 2. D3 prerequisite — exact recovery PASS

Canonical D3 replay:
- Issue: [#2616](https://github.com/yukki0113/GPT/issues/2616)
- Actions run: [44023639295](https://github.com/yukki0113/GPT/actions/runs/44023639295)
- DuckDB: 1.1.3
- two-run byte identity: **true**

Frozen D3 SHA-256:
- `d3_full_condition_evidence.json`: `705a85d4c43b369b14cbba9177f5af13ed3111f1a5031a97ee76acf51064e764`
- `d3_temporal_diagnostic.json`: `27abb3aafabd8b5350009cf8623d43246bda70365427cc772d07e3aba4d8c8bf`
- `d3_run_receipt.json`: `4a128dc02baf4a6ee82a1b560fa1cafb62f540cba8bed38511a97af43c3abd2e`

Library:
- `/BRDB/D3/d3_full_condition_evidence.json`
- `/BRDB/D3/d3_temporal_diagnostic.json`
- `/BRDB/D3/d3_run_receipt.json`
- `/BRDB/D3/restoration_receipt_20261117.json`

All were materialized back and SHA rechecked.

## 3. Real PACI accepted field

PACI:
- archive: `PACI261115.zip`
- Drive file ID: `1wVcoTvNw38nFaPcDWJme-zMsl6MobR3l`
- byte size: **565,352**
- SHA-256: `3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050`

Accepted race:
- race key: **`05265412`**
- target date: 2026-11-15
- venue code: 05
- track type: 1 (raw PACI surface code)
- distance: 2000
- BAC field size: **18**
- KYI declarations: **18**
- UKC joined horses: **18**
- horse numbers: **1 through 18**
- missing sire names: **0**
- missing broodmare-sire names: **0**
- going code: **not supplied / not inferred**

PACI member receipts:
- BAC261115.txt: 6,624 bytes / 36 records / SHA `393fe50cb38eb02e1d9fdffd06fc234a1fdaaba1688a0d6b8fd4ba4495758db6`
- KYI261115.txt: 517,120 bytes / 505 records / SHA `9f439cc0f08cd0a7da86cd7393c89aedeb14cac7d650ca3eea6969b570e159a6`
- UKC261115.txt: 147,460 bytes / 505 records / SHA `ef1f1b8c48cb1f49cad7112331f32a039674ee31ce3d151774c04b7b42733867`

The adapter rejects sentinel/future UKC dates; all 18 accepted profiles passed `data_date <= target_date`.

## 4. Exact committed synthetic gate

The exact PR-branch code executed the committed `test_brdb_d4_paci_field.py`.

Result:
- tests run: **12**
- failures: **0**
- errors: **0**
- skips: **0**
- status: **PASS**

Covered guards include complete field, deterministic ordering, duplicate KYI/UKC rejection, missing UKC rejection, future/sentinel profile rejection, wrong archive date, pre-D3 cutoff, BAC field mismatch, wrong race key and unsupported surface.

## 5. Real D4 sidecar E2E

Owner-created request:
- Issue: [#2617](https://github.com/yukki0113/GPT/issues/2617)
- Actions run: [44024405832](https://github.com/yukki0113/GPT/actions/runs/44024405832)
- artifact: `data-storage-fallback-44024405832` (ID `14302965450`)
- source commit: `333127ba42c012dc406f2c7c5d878dfc99c9f40f`
- fallback status: **PASS**

The sidecar was generated **twice** from identical real PACI context + frozen D3 inputs:
- `two_run_byte_identity=true`
- sidecar SHA-256: `639d6a1c19ec2fb45cffd06fb235f3b659030faa1703c941510af1251acdeefb`

Coverage:
- field size: **18**
- reviewed horses: **18**
- research evidence items: **66**
- horses with zero supplemental evidence: **4** (kept as no evidence; no proxy/fuzzy fill)

Contract:
- `schema_version=brdb-d4-supplemental-research-v0.1`
- `release_status=RESEARCH_SIDECAR_ONLY`
- `research_only=true`
- `prediction_safe=false`
- `historical_asof_status=AS_OF_UNVERIFIED`
- `source_time_status=SAME_DAY_RELEASE_TIME_UNVERIFIED`
- `no_forecast_or_score=true`
- factors remain empty
- summary remains null
- confidence remains `UNASSESSED`
- no exact `score`, `rank`, `probability`, `win_probability` or `forecast` keys generated

## 6. Durable private result storage

Stored in ChatGPT Library:
- `/BRDB/D4/d4_paci_research_context_20261115_05265412.json`
- `/BRDB/D4/d4_paci_source_receipt_20261115_05265412.json`
- `/BRDB/D4/d4_paci_research_sidecar_20261115_05265412.json`
- `/BRDB/D4/d4_paci_e2e_acceptance_receipt_20261117.json`
- `/BRDB/D4/d4_paci_synthetic_test_20261117.log`

All five were materialized back from Library and independently SHA-verified:

| file | SHA-256 |
|---|---|
| acceptance receipt | `7434bc8cea569f8f3e2d872857d6360670d5c9b90753c4ce9925c735988890ad` |
| research context | `c0595775649eb03a31254093d0be6cdd703932fa45e081c7ea822193820d92a0` |
| research sidecar | `639d6a1c19ec2fb45cffd06fb235f3b659030faa1703c941510af1251acdeefb` |
| PACI source receipt | `91cd120b3aa24701d5bf6eae906e3524cc451fe2504e88b7f2b551d56c404b8d` |
| synthetic test log | `0f58707da3fedee7216fed6707a0b77b0a8fae36b492d136518294bf48009786` |

## 7. Acceptance decision

All seven original D4 acceptance gates are satisfied for the **research-only real-PACI full-field E2E**:
1. exact committed synthetic tests PASS;
2. real stored PACI byte/member SHA recorded;
3. one actual full KYI field joined 18/18 to UKC;
4. all three frozen D3 inputs verified and D4 output reproduced twice;
5. future/sentinel UKC, unknown going, provenance and mutation boundaries guarded;
6. research-only / AS_OF_UNVERIFIED / prediction_safe=false retained;
7. row-level context/results stored in Library; Git keeps code/config/audit evidence only.

This acceptance does **not** establish race-off-time publication authenticity and does **not** validate predictive value. Those remain later prospective/time-authenticity stages.

PR #2603 may leave Draft status on this D4 gate; merging it remains a code/research acceptance only, not production graduation.

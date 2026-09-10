# JRDB Edge v0.2 SUGGESTIVE Publication Non-Regression Audit — 2026-09-11

Status: **AUDIT COMPLETE / PASS / STANDARD READY TO ENABLE**  
Scope: Full 2010–2025 fixed artifact from Issue `#833`, plus 2025 pre/post-publication smoke comparison.

## 1. Purpose

Verify that the v0.2 SUGGESTIVE publication layer can be generated from the frozen Full sensitivity result without changing the existing Registry or legacy publication semantics, and that the unified v0.2 serving catalog contains exactly the intended ACTIVE CONFIRMED and 2,000-sample SUGGESTIVE evidence.

This audit does not loosen ACTIVE criteria and does not promote any REJECTED Edge to ACTIVE.

## 2. Source provenance

Full sensitivity source:

- Issue: `#833`
- run_id: `34457918449`
- head_sha: `0539043e8760e1b5941e1a1220821f6a61074a61`
- artifact_id: `10148228167`
- artifact: `jrdb-edge-registry-v02-suggestive-bootstrap-sensitivity-full-2010-2025-a-34457918449`
- artifact digest: `sha256:cfbadfe046d580a822d1f608f6d78a2adf4a46cc1e259ffe29c44ad27945d2e8`

Relevant fixed inputs:

- `edge_registry.sqlite` SHA-256: `17d8528577e2d628a4df57028b0f0e88bbebbaa20699163b0977a2ac0e39600f`
- `edge_suggestive_bootstrap_sensitivity.jsonl` SHA-256: `8f3ae3ab8f8b634f706dc55f8652c7984a6a900529fe74b597dbf98cb935507f`
- SQLite `PRAGMA integrity_check`: `ok`

The frozen sensitivity input contains `519` 400-sample-supported candidates, of which `437` retain support at 2,000 bootstrap samples.

## 3. Full publication reconstruction

The current v0.2 publication contract was applied deterministically to the fixed #833 Registry and sensitivity rows.

Required SUGGESTIVE conditions were rechecked per channel:

```text
registry_status = REJECTED
temporal_status = ACTIVE
statistical_status = WATCH
signal != NEUTRAL
0.05 < q <= 0.10
sensitivity bootstrap samples = 2000
retained same-channel CI excludes zero in the signal direction
```

All `437` retained candidates satisfied the publication invariants. No Edge ID, candidate ID, family, template, q-value, signal, or CI-direction mismatch was found.

Publication counts:

| Publication class | Rows | Performance channels | Value channels |
|---|---:|---:|---:|
| ACTIVE / CONFIRMED | 2,572 | 2,303 | 510 |
| REJECTED / SUGGESTIVE | 437 | 275 | 179 |
| Unified serving catalog | **3,009** | — | — |

SUGGESTIVE composition:

- Performance only: `258`
- Value only: `162`
- Both: `17`
- total supported channels: `454`

ACTIVE composition remains:

- Performance only: `2,062`
- Value only: `269`
- Both: `241`

ACTIVE and SUGGESTIVE Edge ID sets are disjoint. The unified serving catalog contains exactly `3,009` unique Edge IDs.

## 4. Registry status preservation

All `437` SUGGESTIVE publication rows preserve:

```text
registry_status = REJECTED
status = REJECTED
```

No Registry row is rewritten and no SUGGESTIVE row becomes ACTIVE, PROVISIONAL, WATCH, or DECAYING as a consequence of publication.

All `2,572` CONFIRMED serving rows preserve `registry_status=ACTIVE`.

Therefore evidence serving classification remains orthogonal to Registry lifecycle status as required by `JRDB_Edge_Suggestive_Serving_Contract_v0_2.md`.

## 5. Deterministic publication hashes

The Full publication reconstruction produced:

- `edge_registry_suggestive.jsonl` SHA-256: `4812ca292762f096ca1ea5b42bf5d4efbd3a4c94267342d65fbe31592ac40fdc`
- `edge_serving_catalog_v0_2.jsonl` SHA-256: `fe1182e1e8beed952d5f4b740642fd3ec1262c353d6d46036e19a457f27d7469`

These hashes identify the deterministic sidecar publication for the fixed #833 inputs and current builder contract. A later Registry rebuild is expected to produce different hashes and must publish its own audit provenance.

## 6. Legacy publication non-regression

The Full #833 compatibility export was not modified by the sidecar publication audit.

Full #833 legacy files:

- `edge_registry_active.jsonl` SHA-256: `7a372af893df47555a21863b3bb7f88a964a155cf58aab077e625d72131c9469`
- `edge_registry_active.csv` SHA-256: `68460b5696f71772b06dc2302eb2a783539543c6bb1b6cd2bca5ff7ef0567d17`

Despite its historical filename, `edge_registry_active.jsonl` is the compatibility export of all non-REJECTED publication states in this build:

- ACTIVE `2,572`
- PROVISIONAL `64`
- WATCH `1,663`
- DECAYING `74`
- total `4,373`

Its ACTIVE subset exactly matches the `2,572` ACTIVE rows in SQLite.

The new v0.2 unified serving catalog is separate and intentionally contains only ACTIVE CONFIRMED rows plus SUGGESTIVE sidecar rows.

## 7. 2025 pipeline non-regression comparison

A real-data pre/post comparison was also performed between:

- pre-publication sensitivity smoke `#832` / run `34457382556`
- publication-enabled smoke `#836` / run `34491656836`

Core Registry semantic contents were identical:

- `edge_definition`: `1,566` rows, exact semantic equality
- `edge_metric_snapshot`: `6,307` rows, exact semantic equality
- `edge_statistical_guard`: `1,566` rows, exact semantic equality

The legacy JSONL contained `686` rows in both builds. After excluding build metadata fields (`registry_version`, `created_at`, `updated_at`), both sides had the same canonical semantic SHA-256:

`ef5a046647f5b9c5d5f86f2c4100468255379bb341a139d963177c31e8c2c1dc`

Therefore introducing the publication sidecar did not alter 2025 Registry decisions, metrics, statistical guard evidence, or legacy publication semantics.

## 8. Final regression smoke

After adding the new publication and v0.2 serving-matcher tests to the GitHub Actions regression suite, Issue `#837` completed successfully:

- run_id: `34492620969`
- head_sha: `2725756f4cad64e6e82ac3f8803bb4ec80bdbe9e`
- artifact_id: `10158508867`
- artifact digest: `sha256:75368c5b0d15ad09ea996d80aa8adc5ebf582beac75951874c130804190137f0`
- regression tests: `71 passed`
- `suggestive_bootstrap_research`: `0`
- `suggestive_bootstrap_sensitivity`: `0`
- `suggestive_publication`: `0`
- driver exit: `0`

The #837 publication audit also passed with 2025 output:

- ACTIVE rows: `46`
- SUGGESTIVE rows: `4`
- serving rows: `50`
- SUGGESTIVE channels: `4`
- bootstrap samples: `2000`

## 9. Current-matching integration evidence

Before activation, the new v0.2 matcher was exercised against real reconstructed current facts from 2026-09-05 using the Full serving catalog structure.

The STANDARD profile produced non-empty SUGGESTIVE matches while CONFIRMED_ONLY continued to exclude them. Japanese `display_text` remained available for consumer presentation.

This confirms that the publication structure is consumable by the current exact-match path without introducing a second condition-evaluation implementation in the consumer.

## 10. Decision

**PASS.**

The acceptance sequence required by the Serving Contract is now satisfied:

1. 2,000-sample rule frozen;
2. sidecar publication builder implemented;
3. channel-specific evidence implemented;
4. redundancy presentation implemented;
5. legacy publication preserved;
6. focused tests added;
7. 2025 real-data smoke passed;
8. Full fixed-input publication non-regression passed.

No statistical threshold hunting or known-example rescue was performed during publication acceptance.

### Activation recommendation

v0.2 `STANDARD` may now become the ordinary default serving profile, provided:

- v0.1 matcher behavior remains unchanged;
- an explicit `CONFIRMED_ONLY` profile remains available;
- STANDARD consumes `edge_serving_catalog_v0_2.jsonl` when SUGGESTIVE evidence is desired;
- use of the legacy `edge_registry_active.jsonl` remains backward-compatible and naturally yields ACTIVE-only evidence under the v0.2 matcher;
- SUGGESTIVE continues to be labeled lower-confidence and channel-specific;
- no automatic additive scoring is introduced.

Any later change to q-band, bootstrap count, evidence semantics, or redundancy rules requires contract versioning and revalidation.

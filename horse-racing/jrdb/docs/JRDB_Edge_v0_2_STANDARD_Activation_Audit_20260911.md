# JRDB Edge v0.2 STANDARD Activation Audit — 2026-09-11

Status: **ACTIVATION VERIFIED / PASS**  
Scope: v0.2 operational STANDARD serving activation after SUGGESTIVE publication acceptance.

## 1. Purpose

Verify that switching the ordinary v0.2 current-runner entry point to `STANDARD` does not break the existing Registry/publication pipeline, while preserving an explicit `CONFIRMED_ONLY` path and the fail-safe low-level matcher default.

This activation does not change ACTIVE criteria, Registry lifecycle status, SUGGESTIVE statistical eligibility, or v0.1 matcher behavior.

## 2. Activated behavior

Operational entry point:

`src/run_jrdb_edge_match_current_v0_2.py`

Default:

```text
DEFAULT_SERVING_PROFILE = STANDARD
```

The low-level `jrdb_edge_matcher_v0_2` primitives intentionally retain `CONFIRMED_ONLY` as their default. Embedded callers therefore do not silently begin serving SUGGESTIVE evidence merely by importing the updated matcher.

Explicit strict operation remains available through:

```text
--serving-profile CONFIRMED_ONLY
```

STANDARD consumes the v0.2 unified serving catalog and may return channel-specific CONFIRMED and SUGGESTIVE evidence. SUGGESTIVE Registry rows remain `REJECTED` and are not promoted to ACTIVE.

## 3. Prerequisite audits

Activation was allowed only after:

- Full 2010–2025 2,000-sample SUGGESTIVE sensitivity audit passed;
- Full fixed-input publication non-regression audit passed;
- publication builder and v0.2 matcher focused tests were added;
- real-data 2025 publication smoke passed;
- real reconstructed current-facts matching produced non-empty SUGGESTIVE results under STANDARD while CONFIRMED_ONLY excluded them.

Relevant documents:

- `JRDB_Edge_v0_2_Suggestive_Bootstrap_Sensitivity_Full_Audit_20260910.md`
- `JRDB_Edge_v0_2_Suggestive_Publication_NonRegression_Audit_20260911.md`
- `JRDB_Edge_Suggestive_Serving_Contract_v0_2.md`

## 4. Activation smoke

Issue:

- `#838`
- title: `[JRDB_EDGE_REGISTRY_V02] suggestive-standard-activation-smoke-2025-a`
- state: `closed / completed`

Workflow:

- run_id: `34496352854`
- head_sha: `b533a4d1527bc7400e7d02ee0d8035ff1fc1968a`
- status: `success`
- driver_exit_code: `0`
- failed_step: `null`
- failure_class: `null`

All pipeline stages completed with exit code `0`, including:

- feature mart
- discovery
- registry
- statistical guard
- SUGGESTIVE 400-sample research screen
- SUGGESTIVE 2,000-sample sensitivity stage
- SUGGESTIVE publication
- regression tests

## 5. Artifact verification

Artifact:

- artifact_id: `10160062227`
- name: `jrdb-edge-registry-v02-suggestive-standard-activation-smoke-2025-a-34496352854`
- digest: `sha256:a1497cafa12d07321e2d9d818590309ecd06ed9fee9c7738d76c5a8c2ff05fdb`

The artifact contains the expected sidecar serving assets:

```text
edge_registry_suggestive.jsonl
edge_serving_catalog_v0_2.jsonl
edge_suggestive_publication_audit.json
```

as well as the existing Registry/legacy publication assets.

## 6. Regression result

GitHub Actions regression result:

```text
72 passed in 1.63s
```

The suite includes the v0.2 SUGGESTIVE publication tests and serving-matcher profile tests, including the assertion that the ordinary current-runner default is `STANDARD`.

No rollback condition was observed.

## 7. 2025 publication acceptance result

The activation-smoke publication audit reported:

| Item | Result |
|---|---:|
| Registry integrity | `ok` |
| ACTIVE rows | 46 |
| SUGGESTIVE rows | 4 |
| Unified serving rows | 50 |
| SUGGESTIVE Performance channels | 3 |
| SUGGESTIVE Value channels | 1 |
| SUGGESTIVE total channels | 4 |
| SUGGESTIVE bootstrap samples | 2,000 |

Publication audit status: `PASS`.

The publication structure therefore remained valid after STANDARD became the operational default.

## 8. Safety / compatibility boundary

The activation preserves all of the following:

1. `ACTIVE` production statistical thresholds are unchanged.
2. SUGGESTIVE eligibility remains the fixed `(0.05, 0.10]` q-band plus same-channel 2,000-sample directional race-date cluster bootstrap rule.
3. SUGGESTIVE rows preserve `registry_status=REJECTED`.
4. Performance and Value evidence remain separate.
5. `CONFIRMED_ONLY` remains explicitly selectable.
6. Low-level matcher calls retain fail-safe `CONFIRMED_ONLY` defaults.
7. v0.1 matcher behavior is unchanged.
8. No additive Edge scoring is authorized.
9. Current matching remains exact-match and pre-race only.

## 9. Decision

**PASS / ACTIVATION VERIFIED.**

As of 2026-09-11, the ordinary v0.2 current-matching runner may serve the `STANDARD` profile by default.

Operational meaning:

```text
ordinary v0.2 current runner
    -> STANDARD
    -> ACTIVE / CONFIRMED evidence
       + eligible SUGGESTIVE evidence

explicit strict mode
    -> CONFIRMED_ONLY
    -> ACTIVE / CONFIRMED evidence only

low-level matcher default
    -> CONFIRMED_ONLY
```

This closes the SUGGESTIVE serving activation stage. Future changes to the q-band, bootstrap count, evidence semantics, or redundancy behavior require contract versioning and revalidation.

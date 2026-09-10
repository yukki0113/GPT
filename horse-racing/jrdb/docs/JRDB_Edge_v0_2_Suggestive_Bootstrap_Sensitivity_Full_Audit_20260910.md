# JRDB Edge v0.2 SUGGESTIVE Bootstrap Sensitivity Full Audit — 2026-09-10

Status: **AUDIT COMPLETE / SERVING NOT ENABLED**  
Run: `34457918449`  
Issue: `#833`  
Registry version: `edge-v0.2-suggestive-bootstrap-sensitivity-full-2010-2025-a`  
Head SHA: `0539043e8760e1b5941e1a1220821f6a61074a61`

## 1. Purpose

Audit the predeclared SUGGESTIVE sensitivity study on the frozen Full 2010-2025 population from Issue `#827`.

The study does not change Registry status or Matcher serving behavior. It re-evaluates only the channels that were directionally supported by the 400-sample research bootstrap and asks whether the same channel remains directionally supported when bootstrap samples are increased to 2,000.

No q-band, candidate family, known sire, racing maxim, or example was retuned after seeing the result.

## 2. Run / artifact integrity

Issue `#833` completed successfully.

- run_id: `34457918449`
- artifact_id: `10148228167`
- artifact: `jrdb-edge-registry-v02-suggestive-bootstrap-sensitivity-full-2010-2025-a-34457918449`
- artifact digest: `sha256:cfbadfe046d580a822d1f608f6d78a2adf4a46cc1e259ffe29c44ad27945d2e8`
- driver_exit_code: `0`
- `suggestive_bootstrap_research`: `0`
- `suggestive_bootstrap_sensitivity`: `0`
- sensitivity audit `integrity_check`: `ok`

The frozen #827 supported population was reproduced exactly before the 2,000-sample evaluation:

- baseline-supported candidates: `519`
- baseline-supported channels: `540`
- Edge set SHA-256: `a65138340b905f5bd5650ca773346a3262dcd5a62e0bc823e1e5de0d2cea86f4`
- Edge/channel set SHA-256: `bbe29fd342b6a6e9a833612390e4ab39da19b55b2cd9503e26211a5d6fe589b5`

All four frozen identity checks matched the constants preregistered in the v0.2 pipeline before the Full sensitivity run.

## 3. Core non-regression check

The Full #827 artifact and Full #833 artifact were compared locally.

Byte-identical between #827 and #833:

- `edge_candidates.jsonl`
- `edge_registry_active.csv`
- `edge_statistical_guard.jsonl`
- `edge_suggestive_bootstrap_research.jsonl`
- `edge_suggestive_bootstrap_research_audit.json`

SQLite semantic contents are identical for the stable fields of:

- `edge_definition`: `8,182` rows
- `edge_metric_snapshot`: `27,001` rows
- `edge_statistical_guard`: `8,182` rows

`edge_registry_active.jsonl` is not byte-identical only because the build metadata fields changed (`registry_version`, `created_at`, `updated_at`). Edge identities, metrics, guard evidence, and statuses are semantically unchanged.

Therefore the sensitivity stage did not mutate the baseline Registry or the original 400-sample research result.

## 4. Sensitivity result

Baseline 400-sample support:

- candidates: `519`
- channels: `540`

2,000-sample retained support:

- candidates: `437 / 519` = **84.20%**
- channels: `454 / 540` = **84.07%**

Losses:

- candidates losing all supported channels: `82`
- channels losing directional CI support: `86`

The same historical data and same signal direction are used. A lost channel means the 2,000-sample cluster-bootstrap interval no longer excludes zero in the preregistered direction; it does not mean the point estimate reversed direction.

## 5. Channel result

| Channel | 400-supported | 2,000 retained | Lost | Retention |
|---|---:|---:|---:|---:|
| Performance | 347 | 275 | 72 | 79.25% |
| Value | 193 | 179 | 14 | 92.75% |
| **Total** | **540** | **454** | **86** | **84.07%** |

The sensitivity loss is concentrated in Performance: `72 / 86` lost channels (83.72%).

The production Serving Contract must therefore continue to keep Performance and Value evidence separate. A single candidate-level SUGGESTIVE flag would obscure materially different stability.

## 6. Candidate evidence composition after 2,000 samples

Among the 437 retained candidates:

| Retained evidence | Candidates |
|---|---:|
| Performance only | 258 |
| Value only | 162 |
| Both channels | 17 |
| **Total** | **437** |

Thus the intended serving representation remains channel-specific:

```text
performance_evidence_level = CONFIRMED | SUGGESTIVE | NONE
value_evidence_level       = CONFIRMED | SUGGESTIVE | NONE
```

## 7. Family stability

| Family | 400-supported candidates | 2,000 retained | Lost | Retention |
|---|---:|---:|---:|---:|
| COURSE | 22 | 17 | 5 | 77.27% |
| HUMAN | 4 | 1 | 3 | 25.00% |
| PEDIGREE | 445 | 375 | 70 | 84.27% |
| RECENT | 1 | 0 | 1 | 0.00% |
| TRANSITION | 47 | 44 | 3 | 93.62% |

Retained channel counts by family:

- COURSE: Performance `14`, Value `4`
- HUMAN: Performance `1`, Value `0`
- PEDIGREE: Performance `260`, Value `131`
- RECENT: Performance `0`, Value `0`
- TRANSITION: Performance `0`, Value `44`

The retained SUGGESTIVE population remains heavily PEDIGREE-oriented. This study does not justify family-specific threshold relaxation; the same 2,000-sample directional-CI rule is applied uniformly.

## 8. Template stability

Candidate-level 2,000-sample retention:

| Template | 400-supported | Retained | Lost |
|---|---:|---:|---:|
| BROODMARE_SIRE_SURFACE_DISTANCE_V2 | 92 | 69 | 23 |
| COURSE_EXACT_FRAME_V2 | 22 | 17 | 5 |
| JOCKEY_VENUE_DISTANCE_V2 | 4 | 1 | 3 |
| RECENT_ROTATION_SURFACE_DISTANCE_V2 | 1 | 0 | 1 |
| SIRE_AGE_V2 | 21 | 17 | 4 |
| SIRE_BROODMARE_SIRE_V2 | 5 | 4 | 1 |
| SIRE_DISTANCE_CHANGE_V1 | 9 | 6 | 3 |
| SIRE_FRAME_TRANSITION_V1 | 29 | 29 | 0 |
| SIRE_LINE_TURN_DISTANCE_V1 | 9 | 8 | 1 |
| SIRE_SURFACE_DISTANCE_V1 | 67 | 54 | 13 |
| SIRE_SURFACE_TRANSITION_V1 | 9 | 9 | 0 |
| SIRE_TRACK_CONDITION_V2 | 36 | 30 | 6 |
| SIRE_TURN_DISTANCE_V1 | 98 | 86 | 12 |
| SIRE_VENUE_SURFACE_DISTANCE_V2 | 117 | 107 | 10 |

Notably, `SIRE_FRAME_TRANSITION_V1` retained all 29 previously supported candidates; all 29 retained channels are Value channels. This must not be described as 29 confirmed performance effects.

## 9. Polarity stability

Candidate-level result:

| Polarity | 400-supported | Retained | Lost | Retention |
|---|---:|---:|---:|---:|
| POSITIVE | 177 | 135 | 42 | 76.27% |
| NEGATIVE | 330 | 291 | 39 | 88.18% |
| MIXED | 12 | 11 | 1 | 91.67% |

No polarity-specific serving threshold is introduced from this observation.

## 10. q-band and CI-boundary behavior

Channel retention generally weakens as q approaches the upper research bound.

Performance channel retention by q band:

| q band | 400-supported | 2,000 retained | Retention |
|---|---:|---:|---:|
| (0.05, 0.06] | 117 | 98 | 83.76% |
| (0.06, 0.07] | 94 | 83 | 88.30% |
| (0.07, 0.08] | 60 | 46 | 76.67% |
| (0.08, 0.09] | 46 | 31 | 67.39% |
| (0.09, 0.10] | 30 | 17 | 56.67% |

Value channel retention:

| q band | 400-supported | 2,000 retained | Retention |
|---|---:|---:|---:|
| (0.05, 0.06] | 62 | 62 | 100.00% |
| (0.06, 0.07] | 38 | 36 | 94.74% |
| (0.07, 0.08] | 33 | 30 | 90.91% |
| (0.08, 0.09] | 31 | 28 | 90.32% |
| (0.09, 0.10] | 29 | 23 | 79.31% |

The 400→2,000 losses are also concentrated near the zero CI boundary.

Baseline 400-sample directional-bound distance from zero:

- lost Performance median: `0.00143`
- retained Performance median: `0.00497`
- lost Value median: `0.00433`
- retained Value median: `0.03196`

This supports the interpretation that the larger bootstrap mainly removes marginal 400-sample CI classifications rather than invalidating the whole SUGGESTIVE concept.

However, some 2,000-retained Performance channels remain close to zero: `38 / 275` have a directional bound within `0.001` of zero. Therefore 2,000 samples should be treated as the fixed operational bootstrap definition, not as proof of asymptotic convergence.

No ad-hoc CI-margin threshold is added after seeing these results.

## 11. Redundancy / presentation impact after sensitivity

The 437 retained candidates occupy `411` redundancy groups.

- groups with multiple retained SUGGESTIVE candidates: `21`
- retained candidates in those groups: `47`
- groups shared with ACTIVE evidence: `53`
- retained SUGGESTIVE candidates in ACTIVE-overlap groups: `68`
- ACTIVE candidates in those overlap groups: `81`

At channel level:

- retained SUGGESTIVE channels with an ACTIVE-confirmed channel in the same redundancy group: `55`
- same-direction overlap: `52`
- opposite-direction overlap: `5`

Some groups can contain both same-direction and conflicting evidence through different matched definitions. Therefore the existing Serving Contract rule remains necessary: match first, group second; CONFIRMED has presentation precedence over same-direction SUGGESTIVE, while opposite directions remain visible as conflict evidence.

## 12. Sinister Minister sanity check

The original motivating heuristic was not used as an acceptance target.

The previously discussed positive outer-switch rows remain outside the predeclared SUGGESTIVE q band and are not rescued by this study.

Separate Sinister Minister candidates that were independently inside the frozen research band did retain 2,000-sample support, including:

- `OUTER->MIDDLE`: Value NEGATIVE, q `0.05945`, 2,000-sample CI approximately `[-0.3814, -0.0407]`
- several sire/course or sire/turn Performance-positive rows in the q band

This confirms that the study is not reverse-engineered to make the original heuristic appear in serving.

## 13. Audit decision

### Rejected

Do **not** use the original 400-sample bootstrap result directly as the production SUGGESTIVE serving gate.

Reason: a `15.93%` channel attrition rate when moving from 400 to 2,000 samples is material, especially for Performance (`20.75%` loss).

### Recommended current production rule

For a channel to be eligible for future SUGGESTIVE publication, require the existing preregistered conditions plus the **2,000-sample** directional race-date cluster bootstrap result:

```text
final Registry status = REJECTED
temporal_status = ACTIVE
statistical_status = WATCH
channel signal != NEUTRAL
0.05 < channel q-value <= 0.10
2,000-sample same-channel directional race-date cluster bootstrap CI excludes zero
```

This yields the current Full candidate serving population:

- `437` candidates
- `454` supported channels

The 400-sample output remains a research/screening artifact only.

This is still lower-confidence evidence. It is not ACTIVE, not statistically confirmed under the production q<=0.05 contract, and not an independent replication.

## 14. Remaining activation boundary

This audit is sufficient to reject 400 as the ordinary SUGGESTIVE serving criterion and to nominate 2,000 as the fixed v0.2 SUGGESTIVE bootstrap definition.

Before STANDARD serving is actually enabled, the remaining work is implementation/acceptance rather than threshold hunting:

1. update/version the Serving Contract with the fixed 2,000-sample rule;
2. build a separately traceable SUGGESTIVE publication artifact;
3. implement channel-specific evidence fields and redundancy presentation in the v0.2 matcher;
4. keep `edge_registry_active.jsonl` and v0.1 matcher behavior backward-compatible;
5. run focused regression tests;
6. run real-data current-matching smoke;
7. run publication non-regression audit;
8. only then enable the v0.2 STANDARD serving profile.

A later 5,000+ sample audit may be used as an additional numerical-sensitivity check, but it is not used to retune the q band or rescue individual examples. Any future change to the fixed 2,000-sample serving rule requires a contract version bump and revalidation.

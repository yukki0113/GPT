# JRDB Edge v0.2 SUGGESTIVE Bootstrap Full Audit

Status: **AUDIT COMPLETE / SERVING NOT ENABLED**  
Date: 2026-09-10  
Source Issue: `#827 [JRDB_EDGE_REGISTRY_V02] suggestive-bootstrap-full-2010-2025-a`  
Source Run: `34442743305`  
Source Head SHA: `a4f7a4ce29109a18774027c7a95cfd2f52fab82b`  
Artifact ID: `10141174891`  
Artifact SHA-256: `430d06dac4da6f903293c38ec4dd637e46158d0e5a3152174b22a6dc713d443e`  
Comparison baseline: Issue `#822`, Run `34429085356`, Artifact ID `10135816871`

## 1. Purpose

This audit evaluates whether the research-only SUGGESTIVE bootstrap layer can identify useful lower-confidence Edge candidates without weakening the existing ACTIVE statistical contract.

The predeclared research population is limited to candidates that are:

- final Registry `REJECTED`,
- temporal status `ACTIVE`,
- statistical status `WATCH`, and
- have at least one non-neutral signal channel with `0.05 < q <= 0.10`.

Only the selected channel(s) are re-evaluated with the existing race-date cluster bootstrap. The research stage does **not** mutate Registry status and does **not** change Matcher serving eligibility.

## 2. Artifact and non-regression audit

### Result

**PASS**

- #827 workflow completed successfully.
- `suggestive_bootstrap_research=0`.
- Downloaded artifact ZIP SHA-256 exactly matched GitHub artifact digest.
- `PRAGMA integrity_check` on #827 `edge_registry.sqlite`: `ok`.
- #822 baseline Registry and #827 research Registry have identical final status counts:

| Status | #822 | #827 |
|---|---:|---:|
| ACTIVE | 2,572 | 2,572 |
| PROVISIONAL | 64 | 64 |
| DECAYING | 74 | 74 |
| WATCH | 1,663 | 1,663 |
| REJECTED | 3,809 | 3,809 |

Logical comparison between #822 and #827 found:

- Edge ID set: identical, 8,182 / 8,182.
- `edge_definition`: no logical-field differences after excluding run-specific `registry_version` / generated timestamps.
- `edge_metric_snapshot`: 27,001 rows, all fields identical.
- `edge_statistical_guard`: 8,182 rows, all fields identical.
- `edge_candidates.jsonl`: byte-identical SHA-256.
- `edge_statistical_guard.jsonl`: byte-identical SHA-256.
- `edge_registry_active.csv`: byte-identical SHA-256.

Therefore the research stage did not alter Discovery, Registry metrics, ACTIVE membership, or Statistical Guard decisions.

## 3. Research output integrity

### Result

**PASS**

Population:

- temporal-ACTIVE statistical rejects: **3,667**
- q-band selected candidates: **1,015**
- selected signal channels: **1,066**
- candidates with both performance and value channels selected: **51**
- directional-CI supported channels: **540**
- candidates with at least one supported channel: **519**

Every research row was checked against the Registry:

- unique `edge_id`: 1,015 / 1,015
- unique `candidate_id`: 1,015 / 1,015
- expected q-band candidate set vs output candidate set: exact match
- stored p/q values vs research JSONL: exact match within numeric tolerance
- sample / horse / race counts and metric snapshot values: match
- `ci_supports_direction` recomputation from CI bounds and signal direction: match
- candidate-level `bootstrap_supported` equals `any(channel support)`: match
- validation errors: **0**

### 1,014 -> 1,015 correction

A prior exploratory count reported 1,014 candidates in the `.05 < best_q <= .10` bucket. The actual research selector is channel-based, not minimum-q based, so the correct selected candidate count is **1,015**.

The additional candidate is:

`EDGE-B9855C8E5A2327C5686A`

- performance q = 0.047643, but its performance CI had already failed the ACTIVE gate
- value q = 0.064586, which is inside the research band

It is therefore correctly selected through the value channel. This is not a research implementation defect.

## 4. Main result

Of 1,015 selected candidates, **519 (51.13%)** had at least one selected channel whose 95% race-date cluster bootstrap CI preserved the signal direction.

Relative scale:

- selected / temporal-ACTIVE rejects: **27.68%**
- CI-supported / selected: **51.13%**
- CI-supported / temporal-ACTIVE rejects: **14.15%**
- CI-supported / total Registry: **6.34%**
- if all 519 were added beside current ACTIVE, candidate pool would increase by **20.18%** (`2572 -> 3091`)
- relative to ACTIVE + PROVISIONAL, increase would be **19.69%**

This is a material but not explosive candidate layer.

## 5. Channel result

Candidate-level support is not equivalent to one universal Edge strength.

| Candidate support type | Count |
|---|---:|
| PERFORMANCE only | 326 |
| VALUE only | 172 |
| BOTH | 21 |
| NONE | 496 |

Channel-level:

| Channel | Selected | CI-supported | Rate |
|---|---:|---:|---:|
| performance | 784 | 347 | 44.26% |
| value | 282 | 193 | 68.44% |

Signal direction:

| Channel | Signal | Selected | Supported | Rate |
|---|---|---:|---:|---:|
| performance | NEGATIVE | 347 | 184 | 53.0% |
| performance | POSITIVE | 437 | 163 | 37.3% |
| value | NEGATIVE | 262 | 173 | 66.0% |
| value | POSITIVE | 20 | 20 | 100.0% |

**Design implication:** a future Serving layer must preserve performance evidence and value evidence separately. A single `SUGGESTIVE=true` flag is insufficient for user-facing meaning.

Recommended conceptual shape:

```text
performance_evidence = CONFIRMED | SUGGESTIVE | NONE
value_evidence       = CONFIRMED | SUGGESTIVE | NONE
```

The existing ACTIVE/FDR status remains unchanged.

## 6. Family distribution

| Family | Selected | Supported | Support rate | Share of supported |
|---|---:|---:|---:|---:|
| PEDIGREE | 779 | 445 | 57.1% | 85.7% |
| TRANSITION | 116 | 47 | 40.5% | 9.1% |
| COURSE | 93 | 22 | 23.7% | 4.2% |
| HUMAN | 17 | 4 | 23.5% | 0.8% |
| RECENT | 10 | 1 | 10.0% | 0.2% |

Potential increment relative to current ACTIVE by family:

- PEDIGREE: `1450 + 445` = **+30.7%**
- COURSE: `172 + 22` = **+12.8%**
- TRANSITION: `662 + 47` = **+7.1%**
- HUMAN: `91 + 4` = **+4.4%**
- RECENT: `197 + 1` = **+0.5%**

Therefore this experiment is primarily a **PEDIGREE density extension**, not a general solution for HUMAN/RECENT coverage.

## 7. Template distribution

| Template | Selected | Supported | Rate | Current ACTIVE | Supported / ACTIVE |
|---|---:|---:|---:|---:|---:|
| SIRE_VENUE_SURFACE_DISTANCE_V2 | 149 | 117 | 78.5% | 135 | 86.7% |
| SIRE_TURN_DISTANCE_V1 | 156 | 98 | 62.8% | 199 | 49.2% |
| BROODMARE_SIRE_SURFACE_DISTANCE_V2 | 159 | 92 | 57.9% | 215 | 42.8% |
| SIRE_SURFACE_DISTANCE_V1 | 138 | 67 | 48.6% | 289 | 23.2% |
| SIRE_TRACK_CONDITION_V2 | 72 | 36 | 50.0% | 176 | 20.5% |
| SIRE_FRAME_TRANSITION_V1 | 31 | 29 | **93.5%** | 27 | **107.4%** |
| COURSE_EXACT_FRAME_V2 | 78 | 22 | 28.2% | 108 | 20.4% |
| SIRE_AGE_V2 | 55 | 21 | 38.2% | 267 | 7.9% |
| SIRE_DISTANCE_CHANGE_V1 | 51 | 9 | 17.6% | 351 | 2.6% |
| SIRE_LINE_TURN_DISTANCE_V1 | 29 | 9 | 31.0% | 88 | 10.2% |
| SIRE_SURFACE_TRANSITION_V1 | 34 | 9 | 26.5% | 284 | 3.2% |
| SIRE_BROODMARE_SIRE_V2 | 21 | 5 | 23.8% | 81 | 6.2% |
| JOCKEY_VENUE_DISTANCE_V2 | 17 | 4 | 23.5% | 91 | 4.4% |
| RECENT_ROTATION_SURFACE_DISTANCE_V2 | 10 | 1 | 10.0% | 96 | 1.0% |
| COURSE_FRAME_V1 | 15 | 0 | 0.0% | 64 | 0.0% |

`SIRE_FRAME_TRANSITION_V1` is especially notable: 31 research-band candidates produced 29 directional-CI supports. However these are channel-specific results; in this template the research-band signals are value-channel signals rather than a blanket confirmation of frame-transition performance effects.

## 8. q-band sensitivity

Support rate falls smoothly as q moves away from the ACTIVE threshold.

| q band | Performance supported | Value supported |
|---|---:|---:|
| 0.05–0.06 | 117 / 173 = 67.6% | 62 / 65 = 95.4% |
| 0.06–0.07 | 94 / 162 = 58.0% | 38 / 50 = 76.0% |
| 0.07–0.08 | 60 / 144 = 41.7% | 33 / 50 = 66.0% |
| 0.08–0.09 | 46 / 168 = 27.4% | 31 / 51 = 60.8% |
| 0.09–0.10 | 30 / 137 = 21.9% | 29 / 66 = 43.9% |

There is no newly discovered natural cliff inside `.05 < q <= .10`. The upper bound 0.10 should therefore be treated as a **predeclared policy boundary**, not as an empirically optimized threshold.

This is preferable to tuning the cutoff to recover a known horse-racing maxim.

## 9. Nominal p-value sanity check

The bootstrap result was strongly aligned with nominal p-value even though nominal p was not added as a new research gate.

- performance channels with p <= .05: 697 selected / 346 supported (49.6%)
- performance channels with p > .05: 87 selected / **1 supported** (1.1%)
- value channels with p <= .05: 265 selected / 193 supported (72.8%)
- value channels with p > .05: 17 selected / **0 supported**

At candidate level, requiring at least one selected channel with nominal p <= .05 would remove 97 of the 1,015 bootstrap evaluations but would remove only 1 of the 519 current supports.

This is useful as a sanity observation, but no additional nominal-p serving gate is adopted in this audit. Reusing p-value as another pass/fail rule would need an explicit statistical rationale.

## 10. Bootstrap stability caution

The bootstrap implementation is reproducible: it uses a deterministic candidate-ID-derived seed. Re-running the same candidate with 400 samples therefore produces the same output.

However deterministic output is not the same as high Monte-Carlo precision. Among the 347 performance-channel supports, the CI margin beyond zero is often small:

- margin <= 0.001: 53 / 347
- margin <= 0.0025: 128 / 347
- margin <= 0.005: 206 / 347
- median directional margin: approximately 0.00393

Value-channel supports are materially less borderline:

- margin <= 0.001: 1 / 193
- margin <= 0.0025: 9 / 193
- margin <= 0.005: 14 / 193
- median directional margin: approximately 0.02960

Before treating the 519 as a stable production serving set, a one-time sensitivity test with a larger bootstrap sample count is recommended, especially for performance-channel candidates near zero.

The current 400-sample result is suitable as a research screen and is the same default bootstrap scale used by the existing guard, but the lower-confidence tier is by definition concentrated near a boundary.

## 11. Multiplicity / interpretation caution

This research must **not** be interpreted as independent confirmation of 519 Edge hypotheses.

- q-values and bootstrap CIs are derived from the same historical dataset.
- temporal ACTIVE validation provides a separate persistence gate, but the additional bootstrap is still a robustness/uncertainty check on the historical sample, not a new holdout dataset.
- BH-FDR is applied per template and signal family.
- a q-value is not a posterior probability that an individual Edge is true.
- the FDR property of a full `q <= 0.10` rejection set should not be naively transferred to the annulus `0.05 < q <= 0.10` after further filtering.

Therefore `SUGGESTIVE` is an appropriate research label. `CONFIRMED`, `ACTIVE`, or wording implying statistical proof would be inappropriate.

## 12. Redundancy / stacking

Among 519 supported candidates:

- unique `redundancy_group_id`: 487
- redundancy groups containing >1 supported candidate: 26
- supported candidates inside those multi-edge groups: 58
- excess candidates beyond one per group: 32
- candidates with a recorded parent candidate: 117

Existing redundancy grouping therefore removes only a modest fraction of the potential layer.

Because 445 / 519 supports are PEDIGREE and multiple sire-related templates can match the same horse simultaneously, future serving must not treat multiple SUGGESTIVE matches as independent votes or mechanically sum their strength.

## 13. Motivating example: Sinister Minister frame transition

The research rule was deliberately chosen without tuning to the motivating maxim.

Current Full Registry results:

| Condition | performance q | value q | Research selected | CI-supported |
|---|---:|---:|---|---|
| シニスターミニスター INNER->OUTER | 0.203754 | - | No | No |
| シニスターミニスター MIDDLE->OUTER | 0.195638 | - | No | No |
| シニスターミニスター OUTER->MIDDLE | - | 0.059448 | Yes | **Yes** |

The original motivating positive outer-frame-change examples remain outside the `.05 < q <= .10` research band and would **not** be restored by this proposal.

This is a useful sanity check: the experiment has not been reverse-engineered to make the motivating folklore example pass.

A different Sinister Minister pattern, `OUTER->MIDDLE`, does enter the value research channel and its negative value CI remains below zero (`-0.3684 .. -0.0427`). If a future SUGGESTIVE layer is enabled, that evidence must be presented specifically as value evidence, not as a blanket negative performance statement.

## 14. Strength score

The current Registry `strength_score` is not suitable for ranking this layer.

Among the 519 supported candidates, 502 (**96.7%**) have `strength_score=100`.

Therefore a future SUGGESTIVE implementation should not use `strength_score` as the primary discriminator. Raw evidence such as q, directional CI, sample size, effect, and channel identity should remain available.

## 15. Audit conclusion

### What the experiment supports

The proposed concept is viable enough to continue studying:

- it does not require weakening ACTIVE / q<=0.05;
- it reduces 3,667 temporal-ACTIVE statistical rejects to a predeclared research band of 1,015;
- cluster bootstrap further reduces that to 519 candidate-level supports;
- the resulting pool is material but not a several-thousand-candidate flood;
- the motivating folklore example was not artificially recovered.

### What it does not support yet

The audit does **not** justify immediately changing Matcher default serving to include all 519 candidates.

Before production serving, the design should resolve:

1. **Channel-specific evidence:** performance and value must have separate evidence levels.
2. **Label semantics:** SUGGESTIVE must remain explicitly below ACTIVE/CONFIRMED.
3. **Bootstrap sensitivity:** test stability of borderline 400-sample CIs, especially performance.
4. **PEDIGREE concentration / stacking:** consumer-facing aggregation must avoid treating correlated matches as independent votes.
5. **Ranking:** current strength_score is saturated and cannot rank the new layer.

## 16. Recommended next step

Keep Registry status and current Matcher behavior unchanged.

Proceed to a **SUGGESTIVE serving-contract design**, with the research rule provisionally expressed per channel as:

```text
Registry final status = REJECTED
AND temporal_status = ACTIVE
AND statistical_status = WATCH
AND channel signal != NEUTRAL
AND 0.05 < channel q <= 0.10
AND directional race-date cluster bootstrap CI supports that channel direction
=> channel evidence candidate = SUGGESTIVE
```

This should remain a research/serving classification, not a Registry statistical status.

No threshold relaxation to ACTIVE is recommended.

Before enabling default serving, perform a bootstrap-sample sensitivity check and specify how multiple correlated SUGGESTIVE matches are exposed to consumers.

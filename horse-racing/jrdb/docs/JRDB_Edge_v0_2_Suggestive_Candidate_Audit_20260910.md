# JRDB Edge v0.2 SUGGESTIVE Candidate Audit — 2026-09-10

Status: **RESEARCH DESIGN / NO SERVING CHANGE**

## 1. Purpose

Evaluate whether a lower-confidence serving layer can be researched without weakening the existing `ACTIVE` / CONFIRMED statistical contract.

This analysis is intentionally independent of any single known racing heuristic. In particular, no favorite example is used as an acceptance target or to choose a threshold.

Source:

- Issue: `#822`
- Run: `34429085356`
- Registry: `edge-v0.2-status-semantics-full-2010-2025-a`
- Years: `2010-2025`
- Artifact ID: `10135816871`
- Artifact digest: `sha256:d570cb8b6592d5e32aa8529d5f0bdd512577dabfaea47178dc8d9a5c63b13b72`

No Registry status, Matcher behavior, q threshold, or bootstrap threshold is changed by this document.

## 2. Correct statistical-guard execution model

The production guard does not bootstrap every temporal ACTIVE/PROVISIONAL candidate.

Execution order is:

```text
nominal test
  -> BH-FDR q-value
  -> q prepass
       fail -> finalize without bootstrap CI
       pass -> directional race-date cluster bootstrap
                    -> final statistical decision
```

For temporal `ACTIVE`, the current q threshold is `0.05`.
For temporal `PROVISIONAL`, it is `0.10`.

Therefore a null CI among q-prepass failures means **NOT EVALUATED**, not CI failure.

The audit implementation was corrected on 2026-09-10 to preserve this distinction.

## 3. Research population

To avoid mixing maturity problems with statistical-confirmation problems, the first SUGGESTIVE study is restricted to:

```text
final status = REJECTED
AND temporal_status = ACTIVE
```

Population: **3,667 Edge records**.

Family distribution:

| Family | temporal-ACTIVE REJECTED |
|---|---:|
| PEDIGREE | 2,606 |
| TRANSITION | 751 |
| COURSE | 242 |
| HUMAN | 44 |
| RECENT | 24 |
| **Total** | **3,667** |

Polarity distribution:

| Polarity | Count |
|---|---:|
| NEGATIVE | 1,970 |
| POSITIVE | 1,538 |
| MIXED | 159 |

These candidates have already passed their family-specific temporal policy, including the applicable sample, unique-horse/race, segment consistency, effect-direction, and concentration gates.

## 4. q-value distribution

For each record, `min_q` is the minimum q-value among its non-NEUTRAL performance/value channels.

| Best non-neutral q band | Count |
|---|---:|
| `q <= 0.05` | 57 |
| `0.05 < q <= 0.10` | 1,014 |
| `0.10 < q <= 0.15` | 822 |
| `0.15 < q <= 0.20` | 895 |
| `0.20 < q <= 0.25` | 678 |
| `q > 0.25` | 201 |
| **Total** | **3,667** |

Cumulative counts:

- `q <= 0.05`: 57
- `q <= 0.10`: 1,071
- `q <= 0.15`: 1,893
- `q <= 0.20`: 2,788
- `q <= 0.25`: 3,466

The distribution is broad and does not show a natural cliff that would justify choosing `0.15`, `0.20`, or `0.25` as a serving cutoff.

## 5. Existing bootstrap state

Among the 3,667 temporal-ACTIVE REJECTED records:

- bootstrap not evaluated (`bootstrap_samples=0`): **3,610**
- bootstrap evaluated (`bootstrap_samples=400`): **57**

The 57 evaluated records are the `q <= 0.05` cases that cleared the q prepass but failed the final directional-CI gate. They should remain rejected under the current statistical logic and do not need a second identical bootstrap merely to create a lower-confidence tier.

The other 3,610 records cannot be described as CI failures because no production CI was computed.

## 6. Candidate research band: 0.05 < q <= 0.10

The first additional-bootstrap experiment should use:

```text
temporal_status = ACTIVE
final_status = REJECTED
at least one non-neutral channel with 0.05 < q <= 0.10
```

Population: **1,014 records**.

This boundary is not chosen to recover a specific racing heuristic. `0.10` already exists in the current validation contract as the PROVISIONAL q threshold, so it provides an existing policy-relative research boundary rather than a newly fitted cutoff.

Family distribution:

| Family | Candidate count |
|---|---:|
| PEDIGREE | 779 |
| TRANSITION | 116 |
| COURSE | 92 |
| HUMAN | 17 |
| RECENT | 10 |
| **Total** | **1,014** |

Polarity:

| Polarity | Count |
|---|---:|
| NEGATIVE | 549 |
| POSITIVE | 435 |
| MIXED | 30 |

Best-q channel/direction:

| Channel | Direction | Count |
|---|---|---:|
| performance | POSITIVE | 434 |
| performance | NEGATIVE | 327 |
| value | NEGATIVE | 235 |
| value | POSITIVE | 18 |

At least one performance channel has `q <= 0.10` in 784 records.
At least one value channel has `q <= 0.10` in 281 records.
Both channels meet `q <= 0.10` in 51 records.

## 7. Why `strength_score` is not suitable as the new gate

Within the 3,667 temporal-ACTIVE REJECTED records, **3,348 records (91.3%) have `strength_score=100`**.

Therefore current `strength_score` is effectively saturated for this research population and cannot meaningfully distinguish a SUGGESTIVE serving subset.

A new serving tier should not be created by placing another arbitrary threshold on this field.

## 8. Proposed experiment — not yet a serving rule

The next controlled experiment should be:

1. Keep current CONFIRMED/ACTIVE logic unchanged.
2. Keep the 57 `q<=0.05` but directional-CI-failed records rejected.
3. Take only the 1,014 temporal-ACTIVE records in the `0.05 < q <= 0.10` research band.
4. Run the existing race-date cluster bootstrap for this pool using the same canonical effect definitions and direction rules as the production guard.
5. Evaluate performance and value channels separately.
6. Count how many candidates retain a directional CI excluding the neutral value.
7. Do **not** automatically serve them yet; first inspect the resulting family/template concentration and evidence distribution.

A possible later classification, only if this experiment supports it, is:

```text
CONFIRMED
  temporal ACTIVE
  + production q gate
  + directional bootstrap CI gate

SUGGESTIVE
  temporal ACTIVE
  + research q band <= 0.10
  + directional bootstrap CI support
  + production CONFIRMED q gate not cleared

NONE
  everything else
```

`SUGGESTIVE` would explicitly mean lower evidence than CONFIRMED. It would not mean statistically confirmed, and it would not imply positive betting value.

## 9. Serving evidence contract if SUGGESTIVE is later adopted

Any future lower-confidence match should retain separate dimensions rather than collapse them into one buy/sell score:

- evidence level: `CONFIRMED` / `SUGGESTIVE`
- performance signal: POSITIVE / NEGATIVE / NEUTRAL
- value signal: POSITIVE / NEGATIVE / NEUTRAL
- q-value for the relevant channel(s)
- directional bootstrap CI
- sample_n
- unique_horses
- unique_races
- performance lift / baseline rate
- ROI evidence and concentration measures

This allows cases such as **performance tendency exists but betting value is neutral** to be represented directly.

## 10. Empirical Bayes

External review proposed empirical Bayes shrinkage as a stronger long-term method for ranking exploratory effects and controlling winner's-curse inflation.

This is retained as a second-stage research option, not introduced in the first SUGGESTIVE experiment. The first experiment deliberately reuses the existing q and cluster-bootstrap machinery so that the effect of adding a lower-confidence layer can be measured without simultaneously changing the statistical model.

If the bootstrap-supported pool remains too large or unstable, empirical Bayes shrinkage becomes the preferred next refinement rather than further arbitrary q-threshold relaxation.

## 11. Decision at this stage

- Do **not** relax ACTIVE q or CI thresholds.
- Do **not** serve all REJECTED records.
- Do **not** use a known racing heuristic as an acceptance target.
- Do **not** use current saturated `strength_score` as a SUGGESTIVE gate.
- Use the existing `0.10` policy boundary only as a **research prefilter**.
- Next step: additional cluster-bootstrap evaluation of the 1,014 `0.05 < q <= 0.10` temporal-ACTIVE candidates.

No consumer or Registry behavior changes until that experiment is complete and reviewed.

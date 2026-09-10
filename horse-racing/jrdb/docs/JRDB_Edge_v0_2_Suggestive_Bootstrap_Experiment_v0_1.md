# JRDB Edge v0.2 SUGGESTIVE Bootstrap Experiment v0.1

Status: **EXPERIMENT SPEC / NO SERVING CHANGE**
Established: 2026-09-10

## Purpose

Evaluate whether a lower-confidence `SUGGESTIVE` evidence layer can be defined without weakening the existing `ACTIVE` / CONFIRMED contract.

This experiment is independent of any single known racing heuristic. No specific sire, course, transition, or racing maxim is an acceptance target.

## Source population

The research population is restricted to candidates satisfying all of:

```text
final Registry status = REJECTED
temporal_status = ACTIVE
statistical_status = WATCH
at least one non-NEUTRAL channel with 0.05 < q <= 0.10
```

In Full #822 this corresponds to 1,014 candidates.

The q upper bound `0.10` is reused from the existing PROVISIONAL q policy as a research prefilter. It is not a new serving threshold and is not chosen to recover a known heuristic.

## Statistical method

For each selected candidate, reuse the production v0.2 evaluator and the same race-date cluster bootstrap implementation with 400 samples.

Performance and value channels remain separate.

A channel is research-supported only when:

1. the channel itself is non-NEUTRAL,
2. its stored BH-FDR q-value satisfies `0.05 < q <= 0.10`, and
3. its directional bootstrap CI excludes zero in the declared direction.

Candidate-level `bootstrap_supported=true` means at least one research-band channel is directionally CI-supported.

This result is research evidence only. It does not change Registry status, Matcher eligibility, or publication live counts.

## Fail-closed identity check

The study recomputes the nominal p-value from the Feature Mart and requires it to match the p-value stored in the Registry statistical-guard row.

A mismatch fails the experiment rather than mixing Registry evidence with a different Feature Mart/build.

## Outputs

- `edge_suggestive_bootstrap_research.jsonl`
- `edge_suggestive_bootstrap_research_audit.json`
- `edge_suggestive_bootstrap_research_audit.md`

The audit reports selected and directional-CI-supported counts by family, template, polarity, and signal channel.

## Acceptance sequence

1. 2025-only real-data smoke proves the research stage executes with real Feature Mart data and produces outputs.
2. After smoke PASS, run a Full 2010-2025 research build.
3. Inspect how many of the 1,014 Full candidates retain directional bootstrap support.
4. Inspect family/template concentration and performance/value composition.
5. Only then decide whether a `SUGGESTIVE` serving tier is justified.

No serving implementation is authorized by this experiment specification.

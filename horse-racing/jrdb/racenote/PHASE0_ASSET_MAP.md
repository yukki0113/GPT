# RaceNote Reset — Phase 0 Asset Map

Date: 2026-09-28

## A. Freeze / research-history assets

These remain available from the archive branch and existing main history, but are not carried into the new RaceNote specification as forecast logic.

- Forecast Gen0 / Gen0.2 / Gen0.3
- all-runner synthesis
- pairwise comparison
- semantic pairwise / semantic author
- TrendFirst interpretation
- Mark Policy
- Best Bet v0.1
- Edge-aware / Polarity / v1.1 prediction experiments
- blind-mark and betting-layer workflows
- settlement/backtest logic that assumes those marks

## B. Reuse candidates: data/evidence infrastructure

To be audited in Phase 1 before reuse:

- JRDB source parsing / code masters
- historical warehouse
- race and horse history
- RaceReview extraction
- race-day facts
- JRA track facts
- archive/as-of/provenance infrastructure
- raw-vs-warehouse equivalence audits
- reader/zip/archive infrastructure where useful
- firewall separation concepts

Rule:
**Reuse data work; do not inherit forecast conclusions.**

## C. Reuse candidates with forecast leakage risk

Require explicit refactor rather than copy-paste:

- `racenote_general_evidence.py`
- `racenote_horse_evidence_card.py`
- `racenote_scenario_robustness.py`
- `racenote_gen0_2_input_firewall.py`
- old reader/presentation components that expose ranks or marks

## D. Primary design evidence retained for the new project

- manually authored 2023 forecast examples
- discussion-derived principle that RaceNote is a Note, not a prediction algorithm
- local/named-race Trend concept
- broad-vs-local Trend contradiction as useful evidence
- class-preserving fallback for Trend samples:
  - ordinary/condition races: expand using the same class first,
  - OP/graded races with insufficient same-race history: use comparable OP+ context as support.
- blind/pre-result information-separation requirement

## E. Explicitly not decided in Phase 0

The following belong to Phase 1+:

- new RaceNote schema
- exact Trend fields and fallback thresholds
- new/newcomer and steeplechase special handling
- forecast prompt / reasoning guide
- batch orchestration API
- newspaper output contract
- ○▲△ semantics

Phase 0 intentionally stops before these decisions.

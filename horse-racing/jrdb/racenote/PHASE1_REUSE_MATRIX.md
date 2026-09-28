# RaceNote v1 — Phase 1 Reuse Matrix

Date: 2026-09-28

## Reuse directly or with minimal adaptation

| Legacy asset | Phase 1 role | Decision |
|---|---|---|
| JRDB fixed-length parsers / master codes | source normalization | REUSE |
| `racenote_jrdb.py` | PACI -> normalized race/runner facts | REUSE SOURCE LOGIC |
| historical warehouse/readers | as-of history | REUSE |
| `racenote_history_engine.py` | horse history and population stats | REUSE DATA QUERIES, REMOVE FORECAST LABELING |
| `racenote_racereview_adapter.py` | stable RaceReview run evidence | REUSE |
| `racenote_race_day_facts.py` | timestamped race-day facts | REUSE |
| `racenote_jra_track_facts.py` | official weather/track state | REUSE |
| archive/provenance/audit modules | reproducibility | REUSE |

## Refactor before reuse

| Legacy asset | Risk | Phase 1 decision |
|---|---|---|
| `racenote_general_evidence.py` | embeds TrendFirst hierarchy and interpretation lanes | DO NOT REUSE AS CONTRACT; extract only neutral transforms if needed |
| `racenote_horse_evidence_card.py` | contains useful run-level evidence but also direction/priority/strength semantics | REUSE SOURCE OBSERVATIONS ONLY; redesign output |
| `racenote_scenario_robustness.py` | can convert descriptive race structure into forecast consequence | AUDIT LATER |
| `racenote_gen0_2_input_firewall.py` | good boundary concept, schema tied to old bundle | REIMPLEMENT FOR v1 SCHEMA |

## Legacy-only

Do not carry into RaceNote v1:
- baseline rankings
- top-N candidate pools
- pairwise preferred-horse decisions
- semantic author ordering
- Mark Policy
- Best Bet decision types
- Edge/Polarity forecast indices
- betting ticket rules

## Human forecast evidence

`racenote/evidence/human_forecast_evidence_202301.md`

Status: PRIMARY DESIGN EVIDENCE

Use it to check whether the Note preserves the information needed for human-like reasoning.

Do not convert it into deterministic rules.

# EdgeDB v0.4 Research Execution Redesign

Date: 2026-10-05  
Status: ACTIVE RESEARCH PLAN  
Scope: JRDB EdgeDB v0.4 SHADOW research only  
Production impact: NONE

## 1. Why this redesign exists

The scientific intent of EdgeDB v0.4 remains valid:

- discover high-order interactions that are difficult to notice manually;
- treat transition features as first-class evidence;
- exploit pedigree interactions;
- keep Market Value separate from Performance evidence;
- never use current popularity / odds to define the candidate population.

However, the first implementation expanded the search space too early.

Observed history:

- Stage B produced 47,371 search templates.
- Stage C1 full-history r2 evaluated 104 shards.
- r2 merged 4,639,841 research candidates.
- a trailing-5y retry later failed during shard evaluation.

The research process had become dominated by execution cost, artifact size, retry management, and search-space mechanics before answering the important question:

> Does v0.4 discover stable, interpretable and operationally useful Edge evidence?

This redesign changes the order of work.

## 2. Research question

The canonical v0.4 research question is:

> Can pre-race context, transition and pedigree interactions identify a small set of repeatable situations whose performance / value differs materially from broader parent conditions, without depending on one jackpot result or on market-conditioned candidate generation?

The objective is not to maximize historical ROI and not to preserve millions of candidate rows.

## 3. Principles retained from the original design

The following remain hard rules.

1. v0.4 is SHADOW research.
2. v0.2 STANDARD and v0.3 SHADOW production semantics are unchanged.
3. Performance and Value are separate evidence lanes.
4. Popularity / odds are prohibited from candidate generation.
5. Popularity / odds may be used only after population definition for diagnostics / value evaluation.
6. Current-race result information is prohibited from pre-race features.
7. Parent incrementality matters: a deep child condition must add information beyond its broader parent.
8. Jackpot dependency must be measured.
9. Historical discovery and forward / OOS validation must be separated.
10. Raw research evidence may be richer than final presentation evidence.

## 4. Major redesign decisions

### 4.1 Start with trailing 3 years

The first scientific pass uses a trailing 3-year historical window.

Reason:

- current applicability matters more than archaeology;
- pedigree, trainer, course use and racing regimes drift;
- smaller windows reduce compute and reduce domination by obsolete lineages;
- the first goal is to establish whether useful signal exists at all.

The exact range must be derived from the chosen as-of date and recorded in the audit.

### 4.2 Extend to 5 years only if needed

Five years is not the first pass.

Move from 3y to 5y only when the 3y result contains potentially meaningful patterns but support / temporal coverage is insufficient for a decision.

If 3y shows no coherent signal, do not automatically spend compute on a larger search merely to find one.

If 3y shows coherent but underpowered signal, rerun the same frozen definitions over 5y.

No threshold tuning is allowed between the 3y and 5y comparison merely to rescue a candidate.

### 4.3 Do not begin with depth 2-6 exhaustive evaluation

Depth is now progressive.

Wave A:
- depth 2-3;
- transition and pedigree-transition lanes prioritized;
- broad pedigree / static context retained as parent / baseline evidence.

Wave B:
- depth 4 only from prefixes / parent families that survived Wave A research gates.

Wave C:
- depth 5-6 are exceptional research expansions, not default enumeration;
- run only when a lower-depth parent has support, temporal dispersion, and plausible incrementality, and the added dimension has a clear semantic role.

This preserves high-order discovery while stopping blind combinatorial expansion.

### 4.4 Candidate generation and candidate evaluation are separate

Candidate generation remains market-blind.

Evaluation may calculate:

- n
- wins / places
- win / place ROI
- win / place rate
- unique race days
- unique years / periods
- top1 contribution
- ROI excluding top1 / top3
- parent delta
- recent-window consistency
- OOS / rolling survival
- popularity / odds diagnostics after population freeze

Market diagnostics must never feed back into the condition definition.

### 4.5 Compact artifacts are canonical for research decisions

Do not keep millions of rows in Git.

Large row-level candidate artifacts may exist as temporary / external research artifacts, but the Git handoff must contain compact summaries and provenance.

Each stage should produce a compact report containing at minimum:

- input generation / hash / as-of
- window
- lane / depth
- templates evaluated
- observed candidates
- candidates passing each gate
- top failure reasons
- candidate shortlist with metrics
- execution time / memory notes
- artifact identifiers

## 5. New research stages

### R0 — Existing asset audit

Goal:
Reuse as much of the implemented v0.4 pipeline as possible.

Tasks:

- inspect Stage A / B assets and current v0.4 source;
- inspect C1 planner / evaluator / merge;
- determine which parts can accept a 3y window and lane / depth restriction without semantic change;
- identify bugs / assumptions that caused the failed trailing-5y run;
- identify what should be refactored for local / Codex deterministic execution versus Actions-native execution.

No large recomputation in R0.

Deliverable:
compact audit + minimal change plan.

### R1 — 3y Wave A discovery

Scope:

- trailing 3y;
- depth 2-3;
- transition-priority;
- pedigree-transition;
- pedigree baseline / static baseline only where needed as parents.

Goal:
Find whether useful candidate families exist before expanding depth.

Important:
This is a broad scientific screen, not promotion.

Required outputs:

- population counts;
- support distribution;
- candidate counts by lane / depth;
- ROI and hit-rate distribution;
- jackpot dependency distribution;
- parent incrementality where available;
- temporal dispersion;
- a compact research shortlist;
- examples of candidate families that fail for clear reasons.

### R2 — Robustness on R1 survivors

Run expensive diagnostics only on survivors / near-survivors.

Required diagnostics:

- parent incrementality;
- top1 / top3 exclusion;
- temporal split;
- minimum unique days / periods;
- rolling or chronological validation;
- semantic duplicate / nested-condition review;
- sensitivity to modest support changes;
- market diagnostics after candidate population freeze.

Outcome classes:

- PROMISING
- UNDERPOWERED
- JACKPOT_DEPENDENT
- PARENT_REDUNDANT
- TEMPORALLY_UNSTABLE
- SEMANTICALLY_REDUNDANT
- WEAK

These are research labels, not production grades.

### R3 — Decide 3y versus 5y

ChatGPT reviews the R1/R2 result.

Decision:

A. Strong enough to continue:
- keep 3y canonical for this candidate family;
- move to controlled higher-depth expansion / OOS.

B. Plausible but underpowered:
- freeze definitions;
- extend exactly those candidate families to trailing 5y.

C. Weak / incoherent:
- stop that branch;
- do not expand merely because more compute is available.

### R4 — Controlled higher-depth expansion

Only for candidate families approved at R3.

- depth 4 first;
- depth 5-6 only with explicit reason;
- child must show incremental evidence versus parent;
- semantic duplicates must collapse;
- no global blind enumeration.

### R5 — Historical OOS / rolling rehearsal

Candidate definitions are frozen before validation.

Use chronological validation.

Measure:

- survival of direction;
- support;
- ROI / rate degradation;
- parent delta persistence;
- jackpot dependence;
- candidate turnover.

Thresholds must not be retuned on the held-out period.

### R6 — Current PACI shadow match

Only after historical evidence is sufficiently coherent.

Purpose:

- verify pre-race feature availability;
- verify identity / matching;
- observe collision density;
- test presentation compression.

No target result is opened before freeze.

### R7 — Promotion decision

Promotion is a separate decision.

Possible outcomes:

- remain research-only;
- publish v0.4 SHADOW catalog;
- publish only selected families;
- stop v0.4 expansion and retain existing v0.2/v0.3 behavior.

No automatic production promotion.

## 6. Role split: ChatGPT and Codex

### ChatGPT owns research governance

ChatGPT is responsible for:

- defining the scientific question;
- defining stage boundaries;
- freezing comparison rules before seeing later results;
- reviewing Codex outputs;
- deciding whether a branch is PROMISING / UNDERPOWERED / WEAK;
- deciding 3y -> 5y expansion;
- deciding whether depth should increase;
- semantic interpretation / duplicate review;
- protecting Performance / Value / Market boundaries;
- producing the next instruction document;
- approving any SHADOW publication or production proposal.

ChatGPT should not manually perform large repeated aggregation when Codex can run the repository code deterministically.

### Codex owns implementation and heavy deterministic execution

Codex is the default worker for:

- repository inspection across many files;
- refactoring the v0.4 execution path;
- implementing parameters for window / lane / depth / candidate family;
- focused tests;
- deterministic aggregation;
- shard / batch execution where needed;
- performance profiling;
- compact summary generation;
- producing result documents in the collaboration workspace.

Codex must not independently redefine research goals or promote candidates.

If implementation evidence suggests the design should change, Codex records the finding and returns control to ChatGPT.

### GitHub Actions is no longer the default aggregation engine

Use Actions only when an Actions-native reason exists, such as:

- secrets;
- formal immutable publication / audit;
- very large runner-only execution;
- artifact-chain requirements.

Pure deterministic research aggregation should prefer a local / Codex-capable execution path when practical.

## 7. Collaboration contract

Shared workspace:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/`

Flow:

1. ChatGPT writes `instructions/YYYYMMDD_NNN_<topic>_instruction.md`.
2. Codex reads the instruction and canonical references.
3. Codex implements / runs the task.
4. Codex writes `results/YYYYMMDD_NNN_<topic>_result.md`.
5. ChatGPT audits code diff + result.
6. ChatGPT writes the next instruction or closes the branch.

A result document must be sufficient for ChatGPT to make the next research decision without requiring the user to paste console output.

## 8. Initial execution order

The restart sequence is:

1. R0 existing-asset audit.
2. Refactor only what R0 proves necessary.
3. R1 trailing-3y Wave A.
4. R2 robustness for survivors.
5. ChatGPT decision.
6. Only then consider 5y or depth 4+.

Do not restart from a full 2-6-way × all-lane exhaustive C1 run.

## 9. Success criterion for v0.4 research

v0.4 succeeds if it produces a small number of understandable, reproducible, operationally matchable evidence families that add information beyond broader parent conditions.

Success is not:

- maximum candidate count;
- maximum historical ROI;
- deepest cross;
- most elaborate workflow;
- completion of every originally imagined dimension.

A null result is acceptable.

If controlled 3y and justified 5y research fail to produce stable incremental evidence, preserve the current EdgeDB production / shadow system and stop expanding v0.4 rather than data-mine until something looks profitable.

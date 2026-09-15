# Training Edge v0.2 — 2026 OOT Input Route Addendum — 2026-09-15

## 0. Status

This is a **technical execution addendum only** to:

`horse-racing/jrdb/docs/Training_Edge_v0_2_Freeze_20260915.md`

It does not change the frozen scientific contract, target, eligibility, feature blocks, preprocessing, Ridge parameters, calibration, reporting contract, or no-market rule.

- `TRAINING_EDGE_V0_2_SPEC = FROZEN_UNCHANGED`
- `2026_OOT_STATUS = UNOPENED`
- `SCIENTIFIC_FREEZE_COMMIT = 1ae1b424597d391fdca57c8fe826d99df123221b`
- `POST_2026_OPEN_RETUNING = PROHIBITED`

## 1. Why this addendum exists

The Freeze required the OOT workflow input route to be corrected before 2026 metrics were opened. Issue #952 validated public-Drive acquisition for the 2026 PACI/SED target block through 2026-09-13 and also validated the integrity of `jrdb_history_2010_2025.zip`.

A later non-evaluative schema probe, Issue #960, established that the historical Drive SQLite inside that bundle is the generic JRDB Core history database. It does not contain the research-pipeline tables required by the frozen OOT projector / RunPerf pipeline:

- no `training_runner`;
- no `race_context`;
- no `runner_result`;
- no `runner_runperf_features`;
- no `official_runperf`.

The database is valid and useful as a generic canonical history asset, but it is not by itself a drop-in source for the frozen Training Edge OOT execution path.

No Training Edge evaluator was run by Issue #960 and no 2026 model metric was inspected.

## 2. Historical reconstruction route

For the 2010-2025 historical reconstruction layer only, use the already-audited authenticated annual JRDB Raw acquisition path.

Evidence that this route is operational and reproducible:

- Index Base Issue #276 / run `33422716468`: annual 2010-2025 fetch/build/audit all PASS;
- Training Research Issue #831 / run `34449363564`: canonical 2010-2025 research build PASS;
- prior OOT attempt Issue #857 / run `34565399143`: `ANNUAL_FETCH=0`; it failed only at the old 2026 daily fetch, and `evaluation={}`.

This historical acquisition is reconstruction infrastructure. It is not selected or altered from 2026 model performance.

## 3. 2026 OOT target input route

The 2026 target block must use the corrected Drive-first path validated by Issue #952:

- PACI public Drive folder → audited inventory → resilient file-by-file download;
- SED public Drive folder → audited inventory → resilient file-by-file download;
- fixed cutoff `2026-09-13`;
- exact PACI/SED date-set equality through the cutoff;
- PACI → annual-compatible `BAC/KYI/UKC/CHA/CYB` bundles;
- SED → annual-compatible `SED` bundle.

Expected frozen 2026 annual bundle SHA-256 values from #952:

- BAC `f495cf3036cb4f129ea07bb805668c2ff276e8c695800d3e109e6771e224f9f8`
- KYI `7ca1a1eeea1835d0148cf20b409ebc7fcd7c7ba0c1a115d1f71a9fea9431c462`
- SED `07e231282e6b5d86d9085a83dcc9de1e836a0ea6bff1af47732bdc45af83ebed`
- UKC `c5f09d979d34db816723cf63f44afaf34243f95b94085a776de1f77371871413`
- CHA `164804bf36930e94399fbee384259270e8d309bbf54f6bb7b86d7c82f442ca29`
- CYB `e15ea92e4dcb4faffcb094a261d9d49d8d28185e06e62ecf26a8766247b19fd2`

The OOT workflow must fail closed if any hash differs.

## 4. Frozen implementation guard

The execution workflow may run from a later plumbing commit, but before evaluation it must verify that every scientific asset is byte-identical to the Freeze commit:

- `training_edge_v0_2_core.py` blob `fd54df516520a38bbeba895f08a510ebeffa16f8`
- `project_training_edge_v0_2_input.py` blob `a8e38fffc3e426fcd85042fcd7d55765cb0b3e65`
- `evaluate_training_edge_v0_2_oot.py` blob `ee19330559720b148636a451ef6ea8182e766157`
- `training_edge_v0_2_calibration.json` blob `8c0dfb83824c3ddf5aabe4488b50746435acbe62`
- `test_training_edge_v0_2_core.py` blob `bfa42afc8c1bbae56c94856cc11aaa75361e5bd1`
- `test_project_training_edge_v0_2_input.py` blob `47dda84a5dfaebe261670b34a9394c826df91864`

Any mismatch must abort before the evaluator runs.

## 5. Irreversible opening rule remains unchanged

Issue #857 did not open the OOT because its evaluation block was empty. Issue #960 was schema-only.

The first successful production of any 2026 Training Edge v0.2 model metric is therefore still the irreversible opening event. From that moment:

`2026_OOT_STATUS = OPENED_AND_CONSUMED`

No metric-driven v0.2 retuning is permitted afterward.


## RaceNote v0.5.2 mixed-source BTDAY operation — 2026-10-09

- New unused BTDAYs use `RaceNote-Human-Context-Reader-0.5.2-candidate`.
- Canonical procedure: `docs/racenote/RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`.
- Canonical prepare workflow: `.github/workflows/racenote_btday_v052_prepare.yml`.
- Lottery state remains `config/racenote_backtest_day_pool_2026.json`, but it is mixed-source:
  - 2026 -> `source_mode=paci`;
  - 2025 -> `source_mode=historical_warehouse`, accepted generation
    `jrdb_normalized_warehouse_v1_2010_2025_g20260921`.
- Request orchestration must branch by `source_mode`; never fabricate a PACI id for Historical rows.
- Historical transport uses only the reviewed SHA-pinned manifest
  `config/public_drive/racenote_historical_golden_20251228_v1.json` through
  `tools/gpt_io/public_drive/fetch.py`.
- Both branches converge on the same sealed v0.5.2 Reader/session, Decision Core,
  venue save, Freeze and Verify contracts.
- BTDAY-0072 / 2025-12-21 verified the Historical route: 36R / 546 horses,
  DAY PREP PASS, SESSION_SEALED, READY_FOR_V052_AUTHORING.
- The v0.4.6 section below is historical/reproducibility context only.

## RaceNote research-work handoff area — 2026-10-05

Substantial design / execution / audit handoffs are stored under:

`docs/racenote/research-work/`

Use:

- `instructions/` for canonical work orders;
- `reports/` for actual execution/analysis results;
- `audits/` for acceptance/revision decisions.

Current parallel research lane: **RaceNote 0.5.x JRDB Feature Audit**.
The current operational prediction baseline is v0.5.2. The parallel 0.5.x feature audit remains research-only and must not silently alter frozen/current v0.5.2 judgments.
Historical feature analysis must start with **2023-2025** and may extend to **2021-2025** only if the three-year result is inconclusive. If five years still yield no stable practical signal, stop expanding the horizon and retain the 0.4.x Human-Context principle rather than forcing a new feature hierarchy.

Current Stage A instruction:
`docs/racenote/research-work/instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_A_INSTRUCTION.md`

### Legacy RaceNote Human-Context v0.4.6 unified prospective — 2026-10-05

- Historical note: at the time of this section, new unused BTDAYs used `RaceNote-Human-Context-Reader-0.4.6-candidate`. Current operation is v0.5.2 and this section is retained only for reproduction.
- v0.4.6 remains one prediction cohort. 2026-10-05 refinements change prose, trace sparsity and deterministic execution only; they do not change horse-selection semantics.
- Governing prediction context: complete market-blind Reader, integrated race model, ◎○△1△2 ordinary support, independent ▲, final △2 versus closest excluded alternative.
- RRDB is read as contextual evidence, but `rrdb_refs` should include only horses whose RRDB evidence materially changed or sharpened the final judgment. Do not mirror all marked/reviewed horses.
- Reader-facing prose is natural race analysis. Avoid serializing ◎→○→▲→残り△ by habit; translate RRDB/IDM/internal index labels into ordinary racing language unless the raw term itself is genuinely informative.
- Normal execution:
  1. commit `backtests/requests/BTDAY-XXXX.json`;
  2. permanent `.github/workflows/racenote_btday_v046_prepare.yml` builds DAY PREP + clean forecast prep;
  3. model authors one complete `authored_decisions/<venue>.json` and immediately continues;
  4. authored venue files are the recovery points;
  5. permanent `.github/workflows/racenote_btday_v046_finalize.yml` does nothing until all expected venues exist, then performs venue validation/batch materialization -> bind -> Freeze -> Validator -> archive once.
- Normal operation must not create per-BTDAY temporary workflows.
- Saving a venue file is never a reason to ask the user for a continuation instruction.
- Recovery after a genuine interruption starts from the first expected venue without an authored file; saved venues are never re-authored.
- Active schemas:
  - `schema/racenote_decision_core_v0_4_6.json`
  - `schema/racenote_forecast_research_record_v0_4_6.json`
  - `schema/racenote_btday_v046_request.json`
- Canonical docs:
  - `docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_4_6_CANDIDATE.md`
  - `docs/racenote/BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md`
  - `docs/racenote/FORECAST_READER_FACING_PROSE_v0_1.md`
- v0.4.5 chunk/checkpoint modules remain historical/reproducibility assets only.
- Production `current_logic_version` remains unchanged and separate.

### JRDB Daily Raw Acquisition v0.1 — 2026-10-01

- Current routine acquisition contract: `docs/JRDB_Daily_Raw_Acquisition_Operation_v0_1.md`.
- Normal pre-race command: `mmddの開催前取得をお願いします`.
  - acquire target-date PACI;
  - resolve the immediately preceding JRA race week's actual race dates;
  - check canonical Drive SKB inventory;
  - recover/upload only missing preceding-week SKB.
- Normal post-race command: `mmdd〜mmddの開催後取得をお願いします`.
  - acquire/upload SED + HJC for each requested race date;
  - do not request SKB;
  - do not request PACI.
- SKB is intentionally recovered on the following pre-race cycle because its publication timing lags SED/HJC. Same-week SKB `NOT_FOUND` is not a reason for blind retry.
- Always check Drive before upstream fetch, validate artifact ZIP + size/SHA, upload with the native Google Drive connector, then re-list Drive before claiming completion.
- GitHub Actions is used for authenticated JRDB acquisition only; no Actions-to-Drive transport.

### JRDB Result Query v0.1 — 2026-10-01

- Standard completed-race lookup engine: `src/jrdb_result_query.py`.
- GPT/Work standard entrypoint: `src/jrdb_result_query_runner.py`.
- Default: SED top3 + HJC all eight payout types; full runners are opt-in.
- Use this before general Web search for JRDB-covered results/payouts/settlement inputs.
- Historical 2010-2025: accepted Warehouse `sed` + `hjc_payout`; current: SED/HJC Raw.
- Missing source => explicit `partial`; no automatic Web fallback.
- Contract/tests: `docs/README_jrdb_result_query.md`, `tests/test_jrdb_result_query.py`.
- Normal GPT/Work request should need only date, optional venue/race/bet type. First run `jrdb_result_query_runner.py --plan`, materialize the listed Drive SED/HJC with the native connector, then execute the runner. Do not ask the user for artifact paths.
- Repository absence of Raw is expected. Never jump to Web search merely because SED/HJC is not checked into Git.

### Legacy v0.4.6 clean blind daily backtest activation

- Phase: `BLIND_RESEARCH_ACTIVE`; clean-blind picks are allowed.
- DAY PREP entrypoint remains `src/build_racenote_daily.py`.
- Historical v0.4.6 note only. Current BTDAY operation is governed by
  `docs/racenote/RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md` and
  `.github/workflows/racenote_btday_v052_prepare.yml`.
- Target results remain unopened until the full requested forecast scope is
  Frozen and validated.
- RRDB remains contextual evidence under its current recommendation contract.

### RaceNote Daily Build D5 — 2026-09-30

- **D5 PASS / production day-level cutover complete.**
- Standard full-day entrypoint: `src/build_racenote_daily.py`.
- Production chain: `PACI -> BASE -> Analysis/History/Trend/P1/P2 -> RRDB -> Reader View -> validation -> package`.
- Final real-data confirmation: Issue #1611 / run `36646513226`, target 2026-05-23, 36 races / 549 horses.
- All gates PASS: race identity, horse identity, evidence semantic equality, P1/P2, RRDB, Reader View round-trip.
- Reader source hashes are not old-vs-new equality gates because they include expected execution-only metadata differences; migration semantic hashing continues to exclude only `generated_at`, local Analysis paths and query telemetry.
- D5 discovered and fixed a pre-existing indentation regression in `racenote_history_engine.py`; final confirmation ran from main after that source fix.
- Existing one-race paths remain supported for explicit single-race requests, audit and rollback, but are no longer the normal day-level path.
- Historical note: at the time of this D4/D5 infrastructure milestone the Forecast logic was v0.3.2. This is not the current BTDAY logic; resolve current BTDAY logic from `prospective_research_candidate`.
- Audit: `docs/racenote/RACENOTE_DAILY_D5_EQUIVALENCE_20260930.md`.

### RaceNote Daily Build D4 — 2026-09-30

- D4 is implemented in `src/build_racenote_daily.py`.
- Connected path:
  `PACI -> BASE -> Analysis/History/Trend/P1/P2 -> RRDB -> Reader View -> validation -> package`.
- Reader View reuses `racenote_reader_view.py` and every view must pass semantic round-trip before packaging.
- Final output is `RaceNote_YYYYMMDD/authoritative/`, `reader/`, `manifest.json`, and `validation_report.json`.
- Target-result contamination, historical as-of boundaries, RRDB future rows and provenance are fail-closed validation gates.
- `--keep-intermediate` retains only explicit debug material; normal intermediate Stage A/B/C artifacts remain non-canonical.
- Focused tests: `tests/test_racenote_daily_build_d4.py`.
- Status remains **PRE-CUTOVER**. Existing one-race path is production truth until D5.
- Next turn: **D5 — real-data old-path vs daily-path semantic equality and cutover decision**.
- Historical note: at the time of this D4/D5 infrastructure milestone the Forecast logic was v0.3.2. This is not the current BTDAY logic; resolve current BTDAY logic from `prospective_research_candidate`.

### RaceNote Daily Build D3 — 2026-09-30

- D3 is implemented.
- Connected path:
  `PACI -> BASE -> Analysis/History/Trend/P1/P2 -> formal RRDB`.
- New RRDB bulk API:
  `racenote_rrdb_enrichment.enrich_bundles()`.
- All daily horse IDs are collected first; latest-prior Next-Watch is reconstructed once for the whole target date.
- Existing RaceReview adapter / Horse Evidence Card semantics are reused per race.
- `enrich_bundle()` remains backward compatible and shares the same apply helper.
- Daily orchestrator loads frozen Next-Watch rules once and resolves RRDB CURRENT once (or opens one explicit generation root).
- RRDB source failures are request-level FAIL.
- Normal D3 RRDB work uses a temporary directory; retained only with `--keep-intermediate`.
- Focused tests: `tests/test_racenote_daily_build_d3.py`.
- Current CLI intentionally stops after RRDB with `NOT_IMPLEMENTED_AFTER_D3`.
- Existing one-race path remains production truth until D5 equivalence/cutover.
- Next turn: **D4 — Reader View + validation + final package/manifest**.
- Historical note: at the time of this D4/D5 infrastructure milestone the Forecast logic was v0.3.2. This is not the current BTDAY logic; resolve current BTDAY logic from `prospective_research_candidate`.

### RaceNote Daily Build D2 — 2026-09-30

- D2 is implemented in `src/build_racenote_daily.py`.
- Connected path:
  `PACI -> BASE -> Analysis/History/Trend/P1/P2`.
- Stage A reuses `racenote_jrdb.parse_zip / BundleBuilder`; PACI is parsed once.
- Stage B opens Analysis once and calls
  `racenote_history_enrichment.enrich_production_many()` once for all races.
- No History/Trend/P1/P2 logic was reimplemented in the daily orchestrator.
- Current CLI intentionally stops before RRDB with
  `NOT_IMPLEMENTED_AFTER_D2`; it is not production-cutover yet.
- `--keep-intermediate` writes only non-canonical `.debug/history` output.
- Focused tests: `tests/test_racenote_daily_build_d2.py`.
- Migration equality now uses `evidence_semantic_sha256` because independent
  executions necessarily differ in `generated_at`, local Analysis paths and
  query telemetry. Those execution-only fields remain in real artifacts but
  are excluded only from migration comparison.
- Evidence/provenance changes remain hash-significant.
- Existing one-race path remains production truth until D5.
- Next turn: **D3 — resolve RRDB CURRENT/rules once and bulk-enrich all daily races**.
- Forecast logic remains out of scope and unchanged at
  `RaceNote-Human-Context-Reader-0.3.2`.

### RaceNote Daily Build D1 — 2026-09-30

- Goal: make requests such as `09/27のRaceNote生成してください` complete as one deterministic daily build.
- Contract: `docs/racenote/RACENOTE_DAILY_BUILD_v0_1.md`.
- Manifest schema: `schema/racenote_daily_build_manifest_v0_1.json`.
- Skeleton entrypoint: `src/build_racenote_daily.py`.
- Current state: **D1 CONTRACT FROZEN / SKELETON ONLY**.
- D1 production execution intentionally fails closed; `--plan` only.
- No existing RaceNote semantic source was changed.
- Daily stages are fixed as:
  `BASE -> HISTORY/P1/P2 -> RRDB -> READER -> VALIDATION -> PACKAGE`.
- One daily request should parse PACI once, open Analysis once, resolve RRDB CURRENT once, and load Next-Watch rules once.
- Normal output will contain authoritative RaceNote v1.0 bundles + lossless Reader Views + manifest/validation report.
- Intermediate Stage A/B/C outputs are non-canonical and should not be retained by default.
- Cutover is forbidden until D5 old-path vs daily-path semantic equality passes.
- Next implementation turn: **D2 — connect PACI base generation + Analysis/P1/P2 bulk enrichment**.
- Forecast logic `RaceNote-Human-Context-Reader-0.3.2` is out of scope for D1-D5 orchestration work.

### Human-Context Reader 0.3.2 — RRDB reinterpret / recompare — 2026-09-29

- Current calibration logic: `RaceNote-Human-Context-Reader-0.3.2`.
- RRDB role is narrowed to prior-result reinterpretation:
  `visible result -> RRDB reinterpretation -> revised horse understanding -> current-race recompare -> marks`.
- Reinterpretation states: `UPGRADE / DOWNGRADE / CONFIRM / NEUTRAL`.
- RRDB may move marks when candidates are close, when recent form is misleading but relevant direct evidence exists, or when direct evidence is weak/stale/inconsistent.
- RRDB labels alone never justify a mark change:
  - Next-Watch S/A alone: no
  - hidden_strength alone: no
  - fragile_form alone: no
- Strong direct evidence raises the burden of proof but does not make a horse immune to RRDB reinterpretation.
- Old relevant direct evidence may become important again when RRDB explains superficially poor recent finishes.
- CAL-005 should replay the same 10 races / same P1-P2-RRDB inputs as CAL-003/004 so only Reader logic changes.
- No unused eligible PACI day should be consumed.
- If CAL-005 produces both natural RRDB-driven reordering and natural direct-evidence preservation, calibration can be considered for closure before the next fresh two-day blind turn.

### Human-Context Reader 0.3.1 — RRDB balance guard — 2026-09-29

- Current calibration logic: `RaceNote-Human-Context-Reader-0.3.1`.
- Core Human-Context 0.3 behavior is unchanged.
- New RRDB balance guard:
  - RRDB defaults to interpretation / corroboration.
  - decision-neutral RRDB is valid; there is no target RRDB usage rate.
  - RRDB alone cannot overturn strong direct target-condition evidence.
  - a material mark change against strong direct evidence requires an independent current-race reason.
  - `fragile_form` alone is not a veto.
  - `hidden_strength` / Next-Watch S/A alone is not a promotion rule.
  - a directly supported candidate must not be pushed out of the candidate cluster solely by richer RRDB signals.
- CAL-004 should use only already-used/ineligible dates and 10 races.
- If CAL-004 behavior is acceptable, Research may clear CALIBRATION_HOLD and move to the next fresh two-day blind turn.

### RaceNote RRDB formal integration — 2026-09-29

- Design:
  `docs/racenote/RACENOTE_RRDB_INTEGRATION_DESIGN_v0_1.md`
- Status: R1-R5 IMPLEMENTED; focused real-data smoke pending.
- Normal chain:
  `RaceNote base -> Analysis/P1/P2 -> RRDB enrichment -> RaceNote v1.0 -> Reader View -> Human-Context Reader`
- Per-horse block: `racereview`.
- implementation: `src/racenote_rrdb_enrichment.py`
- shared Next-Watch grading: `src/jrdb_next_watch_rules.py`
- production history enrichment can invoke RRDB after Analysis/P1/P2.
- Two lanes:
  - historical Review context
  - latest-prior-start Next-Watch S/A context
- Reuse existing CURRENT resolver / RaceReview adapter / Horse Evidence Card / Next-Watch frozen rules.
- No horse-name fallback; join by JRDB blood registration number.
- Strict historical boundary: `race_date < target_date`.
- RRDB is contextual evidence only: no fixed bonus, no automatic ◎/mark.
- Current future record schema: `schema/racenote_forecast_research_record_v0_3_1.json`.
- Forecast trace records RRDB `reviewed` and whether it was used; if ignored, record why.
- Same-run recent_runs comment + RRDB evidence are corroborating details, not additive votes.
- P3 sibling and obstacle-specific evidence remain out of scope.
- No new clean PACI date should be consumed for RRDB integration validation.

### RaceNote pedigree enrichment feasibility — 2026-09-29

- Obstacle-specific evidence is deferred.
- Pedigree enrichment design:
  `docs/racenote/RACENOTE_PEDIGREE_ENRICHMENT_DESIGN_v0_1.md`
- Confirmed existing project fields:
  - horse_id = JRDB blood registration no
  - sire_name
  - dam_name
  - broodmare_sire_name
  - Analysis also has sire / broodmare-sire line codes
- Implementation status:
  - P1: IMPLEMENTED on main
  - P2: IMPLEMENTED on main
  - P3 sibling history: not yet implemented; requires canonical maternal identity source
- P1 payload exposes sire / broodmare sire / line codes from the approved Analysis target projection.
- P2 adds `pedigree_context` for sire and broodmare sire using target venue + surface + exact distance and target-relevant distance ranges.
- P2 historical rows are strictly `race_date < target_date`; small samples remain visible with sample-size bands.
- `stats.sire` remains backward-compatible and `stats.broodmare_sire` is added.
- P2 is descriptive only: no pedigree score, automatic suitability label, or automatic mark selection.
- Current Analysis v1.4 has no dam_name in that projection, so dam_name remains null / coverage PARTIAL rather than guessed.
- Target-day Analysis access is now restricted to the existing TARGET_COLUMNS pre-race whitelist instead of SELECT * for RaceNote enrichment.
- Do not read arbitrary post-race Analysis rows pre-Freeze; use pre-race source or a dedicated pedigree-only safe projection.
- No pedigree score / fixed weight / automatic mark selection.

### Forecast axis calibration hold — 2026-09-29

- Stop consuming new clean PACI dates until forecast axis is accepted.
- Current phase: `CALIBRATION_HOLD`.
- Current logic pointer: `config/racenote_forecast_logic_current.json`.
- Current logic: `RaceNote-Human-Context-Reader-0.3`.
- Mandatory teacher evidence: `racenote/evidence/human_forecast_evidence_202301.md`.
- Current calibration protocol: `docs/racenote/FORECAST_AXIS_CALIBRATION_PROTOCOL_v0_1.md`.
- Current schema: `schema/racenote_forecast_research_record_v0_3_1.json`.
- Current validator: `src/validate_racenote_forecast_human_context.py`.
- v0.3 forbids single-score / implicit numeric sorting as the primary axis-selection method.
- Use only 6–12 representative races from already-used / ineligible days during calibration.
- BTDAY-0001 dates: 2026-02-08, 2026-05-23.
- BTDAY-0002 dates: 2026-03-08, 2026-04-26.
- Calibration is not blind performance evidence.
- Resume unused two-day turns only after Research thread explicitly clears the forecast axis.


- Forecast reason provenance uses `RaceNote-Decision-Trace-0.1`.
- Decision Trace binds primary / secondary / concern prose to real Trend / RR /
  Ability / Race Structure / Scenario / Edge evidence.
- Scenario risks are derived and cannot be omitted.
- short-comment evidence must be a subset of Decision Trace.
- canonical doc: `docs/racenote/DECISION_TRACE_v0_1.md`.
## Current Drive / source map — 2026-09-23

- New JRDB root: `GPT/horse-racing`.
- Raw: `00_raw`.
- Historical normalized canonical: `10_warehouse/jrdb/v1/current.json`.
- New marts: `20_mart`.
- Old top-level Drive `GPT/JRDB` remains only for legacy Analysis/Fact Lite/Stats/store compatibility; do not delete yet.
- `local-horse-racing` is NAR scope, not the JRDB Warehouse.
- Current placement audit: `docs/JRDB_Source_of_Truth_and_Storage_Map_20260923.md`.

# JRDB thread handoff

Last reviewed: 2026-09-23

この文書は、会話量上限・スレッド分割・担当変更後に **現在のJRDBプロジェクトを短時間で安全に再開するためのbootstrap** です。

固定SHAや一時的な件数を正本化する文書ではありません。再開時は必ず最新 `main` を確認し、対象subsystemのcurrent contract / sourceを読み直してください。

## 1. Restart order

新スレッドでは次の順に確認します。

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. repository root `.gpt/README.md`
3. `horse-racing/jrdb/README.md`
4. `horse-racing/jrdb/.gpt/HANDOFF.md`（この文書）
5. `horse-racing/jrdb/.gpt/CONTEXT.md`
6. `horse-racing/jrdb/.gpt/WORKFLOW.md`
7. latest `main` HEAD
8. 対象subsystemのcurrent docs / contract / audit / source / focused tests

RaceNote開発を再開する場合は、追加で次を読む。

1. `horse-racing/jrdb/docs/racenote/README.md`
2. `horse-racing/jrdb/docs/racenote/FORECAST_GEN0_PLAN.md`
3. legacy確認が必要な場合だけ `horse-racing/jrdb/docs/racenote/legacy/README.md`

会話メモだけを根拠にsourceを変更しません。逆に、古いhandoffや古いdesign docが最新sourceと矛盾する場合は、latest source + current contractを優先します。

## 2. Current architecture snapshot

```text
JRDB Raw / PACI
  -> Common Raw Reader
     ├─> Analysis Lite -> Stats Mart -> Fact Lite / condition-summary PWA
     ├─> RaceNote base -> history enrichment -> RaceNote v1.0 -> Reader View
     │                                                 -> GPT Forecast Gen0
     │                                                    -> pre-result audit / freeze
     │                                                    -> result join / evaluation
     ├─> Eval adapters
     ├─> Canonical / research materialization
     └─> Edge Current Facts -> Edge Matcher
                               -> edge_matches
                                  -> Forecast evidence where explicitly used
                                  -> Newspaper / PWA special memo
```

大きな原則は、**Raw解釈・evidence生成・予想判断・表示・結果評価を分離すること** です。

## 3. Current EdgeDB default

現行は EdgeDB v0.2 STANDARD servingです。

- operational current runner: `src/run_jrdb_edge_match_current_v0_2.py`
- normal default: `STANDARD`
- low-level matcher: `src/jrdb_edge_matcher_v0_2.py`
- low-level default: `CONFIRMED_ONLY` のまま。これは意図したfail-safe
- normal unified serving input: `edge_serving_catalog_v0_2.jsonl`
- current contract: `docs/JRDB_Edge_Suggestive_Serving_Contract_v0_2.md`
- activation audit: `docs/JRDB_Edge_v0_2_STANDARD_Activation_Audit_20260911.md`

絶対に混同しないこと:

- `SUGGESTIVE` はRegistry昇格ではない。通常 `registry_status=REJECTED` のまま
- ACTIVE thresholdをSUGGESTIVEのために緩めない
- Performance evidence と Value evidence は別channel
- Performance-positiveを「馬券妙味あり」と言い換えない
- CONFIRMED / SUGGESTIVEやoverlap Edgeのstrength・ROI・lift・qを加算しない
- current matchingはpre-race exact match。SED結果、着順、払戻、最終オッズ等を混入させない
- Edge current factsのAnalysis history正本はAnalysis v1.3 Parquet current generation。`src/jrdb_edge_analysis_history.py` がvalidated currentをDuckDBでexact lookupする
- SQLite Analysisはrollback / compatibility / equivalence audit専用。通常のEdge current matchingで独立正本として使わない
- TRUE_FORWARD FreezeではAnalysis bundle内 `current.json` が指すgenerationを固定し、generation ID / manifest SHAをprovenanceへ残す
- 2026-09-19実データでSQLite compatibilityとParquet currentの `current_facts.jsonl` / `edge_matches.jsonl` がbyte-identicalであることをIssue #1197 / run 35814265623で確認済み
- consumer側でEdge条件を再実装しない
- v0.1 matcherはbackward compatibility資産。v0.2仕様を直接混ぜない

### EdgeDB v0.3 shadow redesign — 2026-09-24

Production defaultは引き続き **v0.2 STANDARD**。v0.3はshadow research onlyで、Newspaper / RaceNote production servingへ未接続。

Original goal:

- 市場が見落としている、または複雑・多重でまだ市場に十分反映されていない条件を発見し、出馬表へ自動突合する
- broad statistical contextとreader-facing Niche / Market Edgeを同一視しない

Formal operational audit:

- Issue #1230 / run 35885211521
- 対象: 2026-09-12, 09-13, 09-19
- 917runner中 Performance +/-一致 751 (81.9%)
- + / -同時一致 269runner、Performance一致runner内35.8%
- 5件以上68runner、6件以上32runner
- 複数redundancy group 562runner
- COURSE_FRAME_V1 / COURSE_EXACT_FRAME_V2は234回共起し234回同方向

Current v0.3 references:

- operational audit: `docs/JRDB_Edge_v0_3_Operational_Audit_20260924.md`
- shadow design: `docs/JRDB_Edge_v0_3_Granularity_Conflict_Design_v0_1.md`
- semantic map: `config/jrdb_edge_semantic_hierarchy_v0_3.json`
- audit code: `src/audit_jrdb_edge_v02_operational_hits.py`

Design boundary:

- v0.2 Registry / STANDARD servingを破壊・上書きしない
- Context parentとincremental childを分離する
- childはnearest parent / parent-complementに対する追加効果をshadow監査してからNiche候補にする
- PerformanceとValueを別channelのまま保持
- 独立axisの+ / -が残る場合は任意net scoreへ加算せずMIXED
- 次工程はsemantic parent mapを用いたparent-relative metric shadow audit



### 2026 PACI historical backtest lane — 2026-09-29

2026 PACI historical replay is now a separate blinded research lane for
Forecast logic adjustment. The Drive PACI canonical contains 82 race days
from 2026-01-04 through 2026-09-27. Historical tuning must use complete-day
target freezes, one race = one LLM call, immutable Freeze before any target
result open, and separate DEV / OOS / HOLDOUT blocks.

Historical backtest does **not** satisfy the Gen0-G001 TRUE_FORWARD activation
gate.

Canonical design:
`docs/racenote/FORECAST_GEN0_2026_PACI_BACKTEST_DESIGN_v0_1.md`

Canonical config:
`config/racenote_forecast_2026_paci_backtest_v0_1.json`

## 4. RaceNote current prediction direction

> 2026-09-25 current next-generation contract: **RaceNote-Forecast-Gen0.3**.
> Planned first activation: **Gen0-G001**. Gen0.2 was never activated and is
> retained only as a pre-redesign reference.
>
> Pre-Freeze chain:
> `General Evidence -> All-Runner Synthesis -> Pairwise -> Scenario -> Base Forecast -> EdgeDB Performance-only -> Final Forecast -> Freeze`.
> Reading priority: `DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY

Prediction reading layer (2026-09-25):

- `PredictionInterpretation-v0.1` is embedded per horse in General Evidence.
- `RaceNote-All-Runner-Synthesis-0.1` is the canonical full-field draft layer.
- It authors a complete non-scoring draft order after reading every runner.
- Ability cannot be the primary ordering basis.
- low-confidence / mixed / small-sample / RR-contradiction adjacent boundaries become HIGH Pairwise priorities.
- canonical Pairwise request and validation bind to the Synthesis semantic hash and draft order.
- canonical doc: `docs/racenote/ALL_RUNNER_SYNTHESIS_v0_1.md`.
- It organizes trend direction + sample size + redundancy, Race Structure,
  RaceReview hidden/fragile/repeatability/target overlap, and Ability Anchor.
- It does not score or rank.
- Pairwise reads Interpretation first, then verifies raw Evidence lanes.
- canonical doc: `docs/racenote/PREDICTION_INTERPRETATION_v0_1.md`.`.
> JRDB consensus / market / Edge Value / RL-Value / Bet Plan open only after
> immutable Freeze PASS. Training Edge is not a Forecast input.
> Canonical contract:
> `docs/racenote/FORECAST_GEN0_3_PREDICTION_CONTRACT_v0_3.md`

### Gen0-G001 activation readiness — 2026-09-29

The fixed 50 PRIMARY + 20 RESERVE sample manifest is PASS and registered in
`RaceNote Forecast Gen0 検証台帳`. Gen0-G001 is `READY`, not yet `ACTIVE`.
The current operational generation remains Gen0-G000 until the first formal
TRUE_FORWARD pre-result Freeze passes.

Canonical status: `docs/racenote/GEN0_G001_ACTIVATION_STATUS.md`.

Single-race Gen0.3 Prepare transport is also PASS via explicit GitHub Actions
artifact chaining and explicit RaceReview generation binding (Issue #1597 /
Run `36501017523`). No direct Actions -> Drive transport is used by this
single-race activation path. The only remaining Gen0-G001 activation gate is
the first genuine TRUE_FORWARD pre-result Freeze.



RaceReviewDB consumer default (2026-09-25):

- operational source: stable Drive `RaceReviewDB_CURRENT.zip`
- stable file ID: `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`
- resolver: `src/racenote_racereview_current.py`
- normal adapter CLI uses `--racereview-current-cache`
- `--racereview-root` is retained for audit/replay only
- join: JRDB blood registration number; no name fallback
- as-of: `race_date < target_date`
- consumer contract: `docs/racenote/RACEREVIEW_CURRENT_CONSUMER_v0_1.md`
.


RaceNote authoritative bundleは観測データとprovenanceを渡す層です。Reader Viewもprediction modelではありません。

現在の予想研究系は **RaceNote Forecast Gen0** です。

### Forecast logic status — 2026-09-29

RaceNoteの抽出 / evidence contractと、pre-result firewall / provenance /
immutable Freeze / result-after-Freezeの研究手順はcurrent invariant。

一方、詳細な予想ロジックは **UNFROZEN**。

- `RaceNote-Forecast-Gen0.3` = implemented research candidate
- `DATA/TRENDS > RACEREVIEW >= ABILITY` = candidate hypothesis, not adopted default
- Synthesis / Pairwise / Scenario / Edge Performance overlay = candidate components, not mandatory Gen0 steps
- Gen0-G001 activation = PAUSED until Forecast logic selection
- historical PACI backtest = logic selection research
- TRUE_FORWARD = selected logic versionの後段validation

過去のG001 manifest / ledger registration / transport PASSは削除せず、
infrastructure / reproducibility evidenceとして保持する。

### Forecast / Research thread separation — 2026-09-29

- Forecast execution thread = pre-result execution only.
- Research thread = result-open, review, logic research, Git updates.
- execution thread must stop after frozen handoff and must not open target results.

Canonical:
- `docs/racenote/FORECAST_GEN0_THREAD_ROLES_v0_1.md`
- `docs/racenote/FORECAST_EXECUTION_THREAD_BOOTSTRAP_v0_1.md`
- `schema/racenote_forecast_turn_handoff_v0_1.json`

### Forecast baseline observability fix — 2026-09-29

- BTDAY-0001 completed under `RaceNote-Baseline-Reader-0.1`; preserve immutable.
- Before result open, structural audit found insufficient race-specific reasoning trace.
- Current pointer: `config/racenote_forecast_logic_current.json`.
- Current baseline: `RaceNote-Baseline-Reader-0.2`.
- v0.2 keeps no-fixed-weight logic but requires:
  - race thesis
  - 2–4 decisive factors with interpretation
  - explicit ◎ vs ○ comparison
  - strongest counter
  - downweighted evidence
  - reversal condition
- current schema: `schema/racenote_forecast_research_record_v0_2.json`
- trace contract: `docs/racenote/FORECAST_DECISION_TRACE_CONTRACT_v0_1.md`
- pre-Freeze validator: `src/validate_racenote_forecast_decision_trace.py`
- no BTDAY-0001 results were used to create v0.2.

### Current Backtest / TRUE_FORWARD research operating assets — 2026-09-29

The common operating contract is now:

- `docs/racenote/FORECAST_GEN0_RESEARCH_PROTOCOL_v0_1.md`
- `docs/racenote/FORECAST_GEN0_OUTPUT_CONTRACT_v0_1.md`
- `schema/racenote_forecast_research_record_v0_1.json`
- `docs/racenote/FORECAST_GEN0_BASELINE_READER_v0_1.md` — first two-day turn baseline

Historical standard cadence:

- random PICK = 2 unused eligible PACI days
- typically about 48–72 races
- one logic_version for the whole turn
- one race = one independent forecast
- Freeze all usable predictions before any target result open
- review the two days as one turn
- change at most one bounded logic theme before the next turn

Day state:

- `src/racenote_backtest_day_picker.py`
- `config/racenote_backtest_day_pool_2026.json`

User-facing daily output is compact HTML generated only from frozen canonical
records:

- `src/render_racenote_forecast_html.py`
- `forecast_YYYYMMDD.html`

This same common record / presentation contract is intended to carry forward
to TRUE_FORWARD after a detailed Forecast logic version is selected.



正本方針:

- `docs/racenote/README.md`
- `docs/racenote/FORECAST_GEN0_PLAN.md`
- origin reference: `docs/RaceNote_Prediction_Handoff_v0_1.md`

Gen0では、RaceNote v1.0 / validated Reader ViewをGPTが読み、レース条件、基礎能力、条件適性、展開、調教・状態、近走、長期履歴、補助統計、coverageを横比較して予想します。

固定weightや単一gateをcurrent defaultにしません。

```text
pre-race evidence
 -> GPT comparison
 -> prediction
 -> pre-result self-audit
 -> immutable freeze
 -> result acquisition
 -> post-race reading audit
 -> 原則約50R単位の改善
```

### Legacy boundary

過去のv0.2 control / v1.1-P gated predictionは、historical reproducibility / benchmarkとして保持しますがcurrent defaultではありません。

特に以下をGen0の隠れた決定規則として使わないこと:

- top5固定候補
- Good差 `<= 0.04`
- stronger Edge polarityによる機械的な◎昇格
- v1.1-Pの順位をGen0初期順位として無条件継承

詳細は `docs/racenote/legacy/README.md`。

旧系統からは、pre-race guard、as-of boundary、provenance、hash、immutable freeze、result-after-freeze、presentation immutable check等の**検証インフラ**を再利用してよい。予想ロジックと研究インフラを分ける。

### Existing presentation assets

`src/racenote_prediction_presentation_v0_2.py` 等は、freeze済みの旧Edge axis decisionを読者向けへ投影する既存表示資産として残します。

current reader contract:

`docs/RaceNote_Presentation_Comment_Contract_v0_2.md`

これは既存consumer / historical freezeの表示互換に関するcontractであり、v1.1-PをGen0のcurrent prediction policyへ戻す根拠にはしません。

表示層は予想を再計算しません。

## 5. Newspaper / PWA Edge boundary

主要module:

- `src/jrdb_newspaper_merge_edge.py`
- `src/jrdb_newspaper_edge_adapter.py`
- `src/jrdb_newspaper_merge_external.py`
- `src/jrdb_newspaper_publish_current.py`

Newspaperはmatcher outputを受け取るconsumerです。Edge条件を再判定しません。

`jrdb_newspaper_edge_adapter.py` はdisplay boundaryです。

- raw condition / `display_text` / evidenceはaudit用に保持
- reader-facing condition / memoだけを人間向けへ翻訳
- 系統code等の内部codeは、masterで解決できる場合は読者名へ変換
- unknown codeは意味を捏造せずfail-safe / fallback

join identityは `race_key / race_horse_key / horse_no` を中心に扱います。

PWA / Newspaperの都合でForecast policyを決めません。predictionを先にfreezeし、consumerはそのcontractを表示します。

## 6. Post-race Analysis / Mart / Fact Lite

Current Analysis canonical is **v1.4 immutable Parquet**.

Drive root:

`GPT/horse-racing/10_warehouse/analysis/v1/`

Current generation at this handoff:

`analysis-v1_4-canonical-20260928-02`

Current validated coverage:

- 2016-01-05 through 2026-09-27
- 517,622 rows
- canonical key: `race_key + horse_no`
- duplicate key rows: 0

Normal daily candidate path:

`.github/workflows/jrdb_post_race_parquet_refresh_issue.yml`

Native updater:

`src/build_jrdb_analysis_post_race_parquet_native_v1_4.py`

Execution boundary:

```text
previous successful GitHub Actions candidate artifact
  -> Actions-native PACI/SED fetch
  -> v1.4 native Parquet affected-year replacement
  -> audited candidate artifact
  -> GPT downloads artifact
  -> native Google Drive connector publish
  -> Drive round-trip SHA/size/manifest validation
  -> current.json promotion
  -> downstream consumer smoke / Fact Lite / PWA
```

Do not let GitHub Actions read or write Google Drive directly. The post-race
workflow request uses `source_run_id`, `artifact_name`,
`expected_source_generation`, `dates`, and the new
`generation_id`. Drive IDs are not workflow inputs.

Normal v1.4 gates include:

- row count equality
- canonical key equality
- schema contract equality
- row-level equivalence
- metadata preservation
- duplicate key rows = 0
- as-of violations = 0
- native Parquet update = true
- full SQLite materialization = false

Validated first daily cutover:
Issue #1590 / Run `36437363166` -> generation
`analysis-v1_4-canonical-20260928-02`.

RaceNote Trend smoke after promotion:
Issue #1591 / Run `36438532392` -> PASS.

Artifact-only workflow routing smoke:
Issue #1592 / Run `36489888125` -> PASS.

The previous generation remains immutable for rollback. Do not delete the prior
generation merely because `current.json` advances.

The old `jrdb_post_race_refresh_issue.yml` /
`run_jrdb_analysis_post_race_incremental.py` full-SQLite route is legacy /
rollback only, not the normal current path.

Analysisと下流配布は同じ運用世代として扱い、Analysisだけ最新化して
Fact Lite / condition-summary PWAを旧世代へ放置しない。

## 7. Stable data rules

- Fixed-length interpretation: `src/jrdb_raw.py`
- `race_key` は文字列保持。日部分hexをdecimalへ勝手に正規化しない
- `race_horse_key = race_key + horse_no`
- `result_key = blood_registration_no + YYYYMMDD`
- optional joinは原則LEFT / fail-closed
- current predictionはpre-race only
- historical reconstructionはas-of boundaryを必ず守る
- Canonical / Archive / Reader ViewはRaw source truthを置換しない

JRDB codeの意味はマスタコード定義を参照し、数字だけをreader-facing proseへ直接出さないよう確認します。

## 8. Execution routing

詳細は `.gpt/WORKFLOW.md`。現在の標準は以下です。

- **A Read / Audit**: GitHub read/search/fetch。確認目的のIssue不要
- **B Git Change**: source/test/docs/configのUTF-8変更をlatest mainへdirect write
- **C Pure Deterministic Execution**: focused tests、既取得artifact監査、hash/count/join/report
- **D Actions-Native**: Secrets、長時間Full build、immutable freeze/publication、正式run evidence

`[gpt-git-update]` を通常のテキスト修正経路へ戻しません。

旧v1.1-P TRUE_FORWARD workflowがActions-nativeであることと、今後のすべてのRaceNote作業をIssue/Actions経由にすることは別です。新しいGen0作業でも、実行要件に応じてA/B/C/Dを選びます。

## 9. Before changing code or docs

必ず:

1. latest mainを取得
2. path存在確認
3. current content / blob SHA取得
4. relevant contract / sourceの現行状態確認
5. 最小差分を設計
6. write後readback
7. focused test / regression / deterministic audit
8. default・contract・entrypoint・handoff情報が変わった場合はこの文書も更新対象か判定

## 10. Documents that can become stale

次はcurrent truthと決めつけません。

- 日付付きaudit
- 過去Issue本文
- old handoff
- `Status: IN PROGRESS` の旧development note
- fixed artifact ID / run ID / commit SHA
- exploratory counts

これらは履歴・再現性証跡として重要ですが、運用defaultはlatest source / current contractで再確認します。

2026-09-13のv1.1-P TRUE_FORWARD freeze等もhistorical immutable evidenceです。後からGen0形式へ上書きしません。

## 11. What a new thread should be able to answer after bootstrap

最低限、次を再質問せず判断できる状態を目標とします。

- 何がGit正本で何がDrive/Release正本か
- Rawのoffsetをどこで解釈するか
- RaceNote data layerとpredictionの責務境界
- current RaceNote prediction researchがForecast Gen0であること
- v1.1-Pはlegacy logicで、検証インフラだけ再利用可能であること
- EdgeDBのSTANDARD / CONFIRMED_ONLYの違い
- SUGGESTIVEがACTIVEではないこと
- PerformanceとValueを混ぜないこと
- Newspaper/PWAがEdge条件を再計算しないこと
- 読者表示と監査rawを分離すること
- post-race更新後にFact Lite/PWAまで同一世代へ進めること
- GitHub Actionsを使うべき作業とChatで直接行う作業の違い
- 明示的な日次PACI/SED/HJC取得依頼を、既存Raw再利用と区別して安全に実行できること

この項目のどれかが将来変わった場合、source変更だけで終わらせず、README / CONTEXT / HANDOFF / current RaceNote docs / contractのどこへ反映すべきかを同時に確認してください。

## 12. Daily JRDB Raw acquisition / delivery thread

この運用は、ユーザーからの短い依頼、たとえば「0913のPACIを取得」「0905・0906のSEDを取得」に対して、JRDB公式Rawを取得・検証し、ユーザーへinner ZIPを返す定型作業を想定する。

### Scope and intent

- 明示的に「PACI / SED / HJCを取得してください」と依頼された場合は、**fresh official acquisition request** と解釈する。
- この場合は `docs/JRDB_2026_Raw_Drive_Reference.md` の「既存Drive Rawを優先する」という下流処理向け再利用原則より、ユーザーのfresh取得意図を優先し、JRDB upstreamをRoute Dで取得する。
- 一方、Analysis / Eval / RaceNote / research等の処理が「入力として2026 Rawを必要とする」だけなら、Drive inventoryを先にresolveし、既存Rawを再利用する。
- ユーザーが明示的にDrive再利用を指定した場合は、その指定を優先する。
- Raw取得スレッドでは、RaceNote生成、Analysis更新、Stats Mart更新、Edge matching、Eval enrichment等を**自動で続行しない**。追加依頼がある場合だけ別工程へ進む。
- 取得済みRaw / annualized ZIP / Actions artifactをGoogle Driveへ保存する場合は、**connected native Google Drive connectorを使う**。
- `[gpt-gdrive-request]` / `gpt_gdrive_request_issue.yml` / Actions Drive backendは凍結済みで、通常運用では使用しない。
- GitHub artifact -> Driveは「artifact取得 -> Chat/runtime file reference -> native Drive connector」の順で搬送し、Drive bridge用Issueを作成しない。
- Drive routingの上位正本は repository root `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_1.md`。

### Source / workflow

- PACI downloader: `src/fetch_jrdb_paci.py`
- SED / HJC daily downloader: `src/fetch_jrdb_history.py`
- Actions entrypoint: `.github/workflows/jrdb_raw_fetch_issue.yml`
- Issue prefix: `[JRDB_RAW_FETCH_REQUEST]`
- Secrets: `JRDB_USER`, `JRDB_PASSWORD`

PACIは `fetch_jrdb_paci.py --date YYYYMMDD --out-dir <dir>`、SED/HJCは `fetch_jrdb_history.py --date YYYYMMDD --kinds <KIND> --output-dir <dir>` が正本CLI。

### Request contract

Issue bodyはraw JSON。

```json
{
  "date": "YYYYMMDD",
  "kinds": ["PACI"]
}
```

同一日の複数kindを取得する場合は、可能なら1 Issueへまとめる。

```json
{
  "date": "YYYYMMDD",
  "kinds": ["PACI", "SED"]
}
```

異なる日付は別requestとする。

Issue作成前にはlatest mainと `.github/workflows/jrdb_raw_fetch_issue.yml` のparser / accepted kindsを確認する。request JSONは機械的にserializeし、余計なMarkdown fenceをIssue bodyへ混ぜない。

### Success contract

成功コメントmarker:

```text
JRDB_RAW_FETCH_RESULT
```

最低限、次を確認する。

- top-level `status == "success"`
- `manifest.date` が依頼日と一致
- requested `kind` が全てmanifestに存在
- `file_name` が対象kind/dateと一致
- `size_bytes > 0`
- `sha256` が64桁hex
- `members` が空でない
- `run_id` と `artifact_name` が取得可能

### Artifact recovery and local validation

Actions artifactは搬送用outer ZIPであり、ユーザーへ返す標準成果物はその中のrequested inner ZIP。

現在のworkflow layout:

- PACI: artifact展開rootに `PACIyymmdd.zip`
- SED: artifact内 `SED/SEDyymmdd.zip`
- HJC: artifact内 `HJC/HJCyymmdd.zip`

artifact回収後、Chat側で次をPure Deterministic Executionとして行う。

1. outer artifactを展開
2. requested inner ZIPを特定
3. ZIPとして読めることを確認
4. `zipfile.testzip()` 相当でcorrupt memberがないことを確認
5. member一覧を確認
6. local file sizeをmanifest `size_bytes` と照合
7. local SHA-256をmanifest `sha256` と照合
8. ユーザー向けに `/mnt/data/<inner ZIP名>` 等へflattenして返却

ユーザーへ通常返すのは `PACIyymmdd.zip` / `SEDyymmdd.zip` / `HJCyymmdd.zip` であり、`jrdb-raw-YYYYMMDD.zip` outer artifactではない。

### Failure / retry rule

- generic failure commentだけを見て「未公開」「データなし」と推測しない。
- failed step / job logを確認し、認証、HTTP status、parser、ZIP validation、artifact upload等のどこで失敗したかを特定する。
- `404` 等、upstream不在を直接示す観測がある場合だけ、その事実を報告する。
- 同一requestをblind rerunしない。latest mainとfailed stepを確認してからretryする。
- retry時も、取得そのもの以外の確認・SHA比較・ZIP検査のために追加Issueを作らない。

### Delivery report

正常時の最終報告は簡潔でよいが、最低限次を含める。

- 対象日 / kind
- inner ZIPへのダウンロードリンク
- ZIP破損検査結果
- member数またはmember確認済みである旨
- SHA-256
- Actions manifestとの一致

このsectionは、日次Raw取得専用スレッドへ引っ越した際に、過去会話を参照しなくても同じ安全な取得・検証・返却手順を再現するための運用正本とする。
## Analysis / Fact Lite dual-format transition

- `migrate_jrdb_analysis_parquet.py` creates immutable year-level ZSTD
  objects, preserves the two Analysis metadata tables, and writes only
  `shadow_current.json` after full logical equality checks.
- `materialize_jrdb_analysis_sqlite.py` is the compatibility route back from a
  validated Parquet manifest; it is not an independent update path.
- `build_jrdb_pwa_fact_lite_dual.py` produces PWA-compatible SQLite and a
  Parquet twin from one DuckDB relation.  `audit_jrdb_pwa_fact_lite_dual.py`
  is the required Legacy SQLite == New SQLite == Parquet gate.
- Do not change `jrdb-pwa-fact-lite-current`, Pages, sql.js, or OPFS until an
  explicit real-data audit and publication cutover has passed.


## JRDB normalized Warehouse finalization — 2026-09-21

- Dedicated pointer: Drive `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`.
- It is independent of NAR canonical `CURRENT.json`; never overwrite or consume that pointer as JRDB state.
- Accepted generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`, 10 families, 2010–2025, 192 immutable staging-object references; final audit PASS and duplicate object count 0.
- Resume/read order: JRDB `current.json` → referenced final `manifest.json` and `audit.json` → family staging only for provenance/evidence.
- The finalizer is `src/finalize_jrdb_warehouse_from_staging.py`; operations contract is `docs/JRDB_Normalized_Warehouse_Operation_v1.md`.
- Do not regenerate, copy, or reupload accepted family Parquet. PACI/Analysis/RaceNote/Eval/backtest consumer cutover is a separate subsequent task.


## Analysis input: Warehouse dual-read staged — 2026-09-21

Historical Warehouse-to-Analysis code is staged, not yet promoted. The reader (`src/jrdb_analysis_warehouse_adapter.py`) and non-mutating equivalence audit (`src/audit_jrdb_analysis_raw_vs_warehouse.py`) preserve the existing Analysis schema and Raw adapter semantics. Use the dedicated 2010–2025 Warehouse pointer only.

Do **not** switch the normal 2026 PACI/Raw incremental path: the accepted historical Warehouse has no 2026 coverage and PACI daily is explicitly out of scope. A historical date may use `update_jrdb_analysis_incremental.py --warehouse-current ...` only after the exact Raw-direct vs Warehouse audit is PASS for the same source delivery. Raw-direct remains the rollback/audit path. Contract: `docs/JRDB_Analysis_Warehouse_Input_Contract_v1.md`.


## Analysis input: accepted Historical / Current split — 2026-09-21

The formal dual-read gate is PASS: seven Raw deliveries across 2010, 2018, and 2025, 2,866 rows total, with equality of row count, primary key, schema, NULL/blank semantics, all 34 logical columns, canonical row hashes, representative queries, and repeated same-day replacement.

- **2010–2025 historical backfill/rebuild:** dedicated JRDB Warehouse `current.json` → Warehouse Analysis reader → unchanged Analysis Lite v1.3 output.
- **2026 current daily update:** PACI / SED Raw-direct → existing Analysis path; this remains unchanged.
- Historical Raw-direct is retained for rollback/audit only and needs explicit `--allow-historical-raw`.
- The Warehouse reader rejects dates outside the accepted 2010–2025 coverage; do not use it for 2026.
- Neither the JRDB Warehouse pointer nor the existing Analysis current pointer changed in this cutover.

Operational contract: `docs/JRDB_Analysis_Warehouse_Input_Contract_v1.md`. Formal evidence: `docs/JRDB_Analysis_Warehouse_Dual_Read_Audit_20260921.md`.


## RaceNote Historical Warehouse Phase 1 — 2026-09-22

- Historical RaceNote rebuild input is now the accepted JRDB Warehouse generation `jrdb_normalized_warehouse_v1_2010_2025_g20260921`, resolved through the dedicated JRDB current contract; do not use or alter any NAR pointer.
- `jrdb_racenote_warehouse_reader.py` reads immutable Parquet via DuckDB and feeds the unchanged `racenote_jrdb.BundleBuilder`. `audit_jrdb_racenote_raw_vs_warehouse.py` is the formal dual-read gate.
- 2018-12-28 and 2025-12-28 passed row/key/schema/NULL-blank/all-logical-value/semantic-hash/repeated-read/idempotence checks. The Raw audit must use `ZED/ZKB`, not `SED/SKB` substitutions.
- The 2010 KYI archive has 65,835 references to 2009 results (and older references); keep the explicit Raw boundary fallback and provenance. Never silently downgrade other historical Warehouse requests to Raw.
- 2026 current daily remains PACI/Raw. Warehouse coverage is fail-closed at 2010–2025.


RaceNote Gen0.3 real-data dry run (2026-09-25):

- `docs/racenote/GEN0_3_REALDATA_DRYRUN_HATSUKAZE_20260913.md`
- 2026-09-13 中山10R 初風SをFreezeまで完走。
- result-open後の1R結果は不振だったため、単発結果で重み調整はしない。
- next research: Trend materiality / MIXED conflict detail / Ability floor guard study / Scenario provenance.
## RL-T Production Historical Warehouse cutover handoff — 2026-09-26

Production plumbing cutover is complete.

```text
DAILY_HISTORICAL_SOURCE             = WAREHOUSE
REPLAY_HISTORICAL_SOURCE            = WAREHOUSE
TRAINING_RESEARCH_UPSTREAM_SOURCE   = WAREHOUSE
HISTORICAL_RAW_NORMAL_FETCH         = 0
HISTORICAL_RAW_FALLBACK             = DISABLED
2026_ROUTE                          = UNCHANGED
STATIC_CUTOVER_AUDIT                = PASS
FIXED_DATE_REPLAY_SCORER_SMOKE      = PASS
TRAINING_RESEARCH_BUILD_SMOKE       = PASS
```

Evidence:
- Issue #1520 / run `36242350903`: production static audit PASS
- Issue #1517 / run `36240031550`: 2026-09-20 replay/scorer SUCCESS
- Issue #1518 / run `36240033827`: Warehouse Training Research chain SUCCESS

Do not restart Warehouse, Index Base equivalence, record-hash compatibility, or Stage2b Parquet migration work.

Separate follow-up:
- Issue #1521 tracks current-forward runtime fingerprint drift seen on 2026-09-27.
- The 2026-09-27 run passed Historical Warehouse preparation, current Drive acquisition, bundling, hybrid Index Base, RunPerf, Official RunPerf, and projection, then failed closed at the unchanged frozen runtime fingerprint.
- Do not solve this by changing frozen science or restoring Historical Raw as a production fallback.

## RaceReviewDB recommendation cutover — 2026-10-01

Current RRDB recommendation contract:

- `docs/RaceReviewDB_Recommendation_Operation_v0_2.md`
- `src/jrdb_recommendation_signals.py`
- contract version: `rrdb-recommendation-signals-v0.2`

Operational recommendation signals:

- `TIME_CLASS_PLUS1` — 上位クラス時計
- `FRONT_SURVIVE_GAP05` — 前傾を前で受けて勝ち馬0.5秒以内
- `REAR_HIGH_LAST3F90` — 後傾後方＋上がり90pct以上
- `HV01` — 4着以下＋補正タイム上位20%
- `HV02` — 6着以下＋補正タイム上位20%

S/A recommendation grade is **disabled**. Multiple matched signals do not automatically increase rank. Consumers should expose the measured strength values of each signal instead.

Current source-date selector:
`src/jrdb_recommendation_select.py`

Current future-PACI reverse lookup:
`src/jrdb_recommendation_reverse.py`

Normal recommendation/history lookup horizon is `730 days` before the target date. This is a consumer-serving boundary, not permission to delete the longer RRDB research/computational history. The incremental Review builder currently seeds standards from persisted CURRENT history, so physical CURRENT compaction must not be done until baseline-history state is decoupled.

The former `jrdb_next_watch_rules.py` S/A contract and `next-watch-rules-discovery-v0.1` artifact are historical-reproduction assets only.

## RL / RaceLift retirement handoff — 2026-10-02

RL research is retired. Do not resume model development or daily index generation from the older RL-T handoff sections.

Normative contract:
`docs/RL_Retirement_Contract_20261002.md`

```text
RL_RESEARCH_STATUS               = RETIRED
RL_DAILY_INDEX_GENERATION        = STOPPED
RL_INDEX_REQUIRED_BY_PRODUCTION  = FALSE
RL_T_V0_2                        = FROZEN_REPRO_ONLY
TRAINING_RESEARCH                = FROZEN_RESEARCH_ASSET
```

Important:

- Missing RL / Training Edge output is a valid normal state.
- Do not create an RL value on demand for Newspaper, RaceNote, EdgeDB, or PWA.
- Do not restart Training Research, HOLDOUT, OOT, runtime freeze, or model-tuning work unless a new explicit research decision reopens RL as a new version.
- Keep Warehouse / Index Base / record-hash compatibility active; those are shared JRDB infrastructure.
- Existing anti-RL RaceNote firewalls should remain.
- Historical RL docs and evidence should be read as frozen research history, not as current next-action instructions.

Next cleanup sequence:
1. retire active RL workflows,
2. prove downstream non-dependency,
3. inventory/freeze RL assets,
4. disentangle shared infrastructure naming where useful,
5. run final retirement audit.

## RL retirement T2 handoff — 2026-10-02

T2 is complete.

- RL model/research/Training Research active Actions entrypoints: 0
- RL daily/replay active Actions entrypoints: 0
- RL research open issues: 0
- archived retired workflows: 8
- shared Warehouse / record-hash `rlt_*` workflows remain active intentionally

Evidence:
`docs/RL_Retirement_T2_Workflow_Audit_20261002.md`

Next cleanup turn is T3: prove Newspaper / RaceNote / EdgeDB / PWA have no hard
dependency on RL and ensure no active workflow passes `--my-index-csv`.

## RL retirement T3 handoff — 2026-10-02

T3 is complete.

```text
RACENOTE_RL_REQUIRED            = FALSE
NEWSPAPER_RL_REQUIRED           = FALSE
EDGEDB_RL_REQUIRED              = FALSE
PWA_RL_REQUIRED                 = FALSE
ACTIVE_MY_INDEX_ARGUMENT_COUNT  = 0
T3_DOWNSTREAM_NONDEPENDENCY     = PASS
```

Evidence:
- Issue #1720
- run `36949876100`
- artifact `11203452444`
- report: `docs/RL_Retirement_T3_Downstream_Audit_20261002.md`

Keep `src/audit_rl_retirement_downstream_dependencies.py` for the final T6 audit.
The temporary T3 Actions workflow was removed after PASS, so no new active RL workflow remains.

Next: T4 — inventory and freeze RL research assets. Do not delete shared Warehouse / Index Base infrastructure.


## RL retirement T4 — 2026-10-02

T4 is complete. Inventory: docs/RL_Retired_Asset_Inventory_20261002.md.

- RL source/config/tests are FROZEN_REPRO_ONLY; Training Research is a FROZEN_RESEARCH_ASSET.
- Dated research docs and the old runtime pending marker are historical evidence, not current tasks.
- No RL research asset was deleted; accepted Training Research Parquet/evidence remains preserved.
- Shared Warehouse / Index Base / record-hash compatibility and common DuckDB/Parquet tooling remain active.
- Gate: T4_ASSET_FREEZE = PASS.

Next: T5 shared-infrastructure naming/role audit; preserve active JRDB Warehouse and record-hash workflows.

## RL retirement T5 — 2026-10-02

T5 is complete. The five active rlt_* workflows and prepare_rl_t_historical_warehouse_inputs.py remain by name with explicit ACTIVE_SHARED_INFRA role comments. Names/issue prefixes remain for compatibility; functional behavior is unchanged. No active rlt workflow generates RL output. Audit: docs/RL_Retirement_T5_Shared_Infrastructure_Audit_20261002.md.

SHARED_WAREHOUSE_INFRA_ACTIVE = TRUE
SHARED_INDEX_BASE_ACTIVE = TRUE
RECORD_HASH_COMPAT_ACTIVE = TRUE
RL_ONLY_SHARED_INFRA_COUNT = 0
AMBIGUOUS_RLT_ACTIVE_ROLE_COUNT = 0
T5_SHARED_INFRA_DISENTANGLEMENT = PASS

## RL retirement T6 — COMPLETE — 2026-10-02

Final report: docs/RL_Retirement_Final_Report_20261002.md.

- T1–T6 all PASS; RL retirement is COMPLETE.
- Formal audit run 36961003878 succeeded at head 621ad3a961e050d3b12672add4aae3290bd33037; artifact 11206784733, digest sha256:437e34ecef5afedb9f1f51327a4ad190fad6e16f0ea1f578eacacfa251bf67cd.
- Active RL model/daily/research workflow counts = 0; RL research open issue count = 0; downstream hard dependency count = 0.
- RL assets and reproduction evidence are preserved; shared JRDB Warehouse / Index Base / record-hash compatibility remain active.
- Temporary T6 workflow was removed after PASS; permanent audit scripts and report remain.

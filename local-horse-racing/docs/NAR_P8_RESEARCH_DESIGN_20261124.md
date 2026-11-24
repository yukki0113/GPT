# NAR P8 研究設計 v1.0 — 2026-11-24

Status: DESIGN / NOT_EXECUTED. ユーザー指示により復旧系統を正式な研究ルートに採用する。旧v0.1.0/v0.1.1の復元は終了し、旧成果の再探索を前提としない。旧ラベルを再利用しない。RECOVERY-PILOT-r0.1は不変の比較基準であり本番採用ではない。REC-P8A/B, REC-P9, REC-P10をP8A/B, P9, P10へ改称する。本書はP8設計の正本候補。P8実行・本番昇格・Canonical変更は未実施。

## 1. Purpose / scope

3軸のうち基礎能力 A と会場・条件適性 C を分離して検証する。P8Aで基礎能力・比較可能性、P8Bで今回条件との相性・展開を研究。騎手・厩舎・ライン・血統の新規補正はP9、統合・回収率はP10。市場Edge、映像、2026年データ、PENDING snapshotの昇格は対象外。まずダート平地（ばんえい・芝等は別体系）。対象会場/種別は実データの値を棚卸しして明示する。

## 2. Input / source contract

- GitHub `local-horse-racing/docs/CANONICAL_DATA_SPEC.md` P0.1契約、`config/canonical_integrity_corrections.json`、共通 `.gpt/GITHUB_OPERATION_POLICY.md` を優先。CURRENTからaccepted/published世代を取得、今回固定世代 `nar_canonical_v1_201601_202512_g20260917`、manifest SHA256 `bdc6cc603f5a199fa513bffea3b0450588df828c0bdbac5c52e980f4ab6f926a`。
- 2016〜2025の `pre/race`, `pre/runner`, `post/runner_result`, `control/race_status` (40 partition); P8Bで `post/race_result` (10) を追加。取得時にmanifest/ledger SHA・サイズ・行数・schema・key uniqueness・join cardinalityを照合。既知P0-01訂正は厳密条件以外fail-closed。`post/payout` と `pre/runner_history_snapshot` はP8に搬送しない。
- ENTRYモデルを本線。対象日Dの前日以前だけの履歴（D-180 <= history_date < D、他の窓も同じ上限）。過去の馬場・天候は過去条件として可、対象の馬場・天候はENTRY不可。RACE_DAYは別研究branch、当時観測時刻不明なら厳密な実運用評価と区別。馬体重は対象外。対象結果・当日他R・未来・対象control・人気・オッズ・払戻・PENDING8種禁止。月次確定版の回顧評価であって当時版出馬表の完全再現ではない。既知の遅延/訂正情報は除外。
- 共通Data Storage正本を利用、registryでruntimeを確認。Parquet ZSTD、年partition、DuckDB in-process。全raw/postをscore工程に渡さず、history builder / feature freeze / score freeze / evaluator を分離する。

## 3. Chronological evaluation contract (before first execution)

| Period | Role |
|---|---|
| 2016 | warm-up; no headline evaluation |
| 2017–2021 | development / annual expanding walk-forward; any fit uses dates before evaluation fold |
| 2022–2023 | validation; compare pre-registered variants and select once |
| 2024–2025 | locked retrospective confirmation; no parameter tuning or subgroup rule creation on these outcomes |
| 2026 | untouched by P8/P9; only later independently approved canonical extension and freeze protocol |

2025 H2 pilot is already known and lost research may have used other years; 2024–25 is NOT an independent blind holdout. P8A and P8B choose candidates on development/validation; 2024–25 confirmation after both configs are frozen, once per registered family, and no tuning afterward; if already opened, report as exploratory. Past results within a fold can update rolling state for later dates; coefficients/variant choice remain frozen. Candidate comparison on same race/runner support, and separate full eligible cohort including abstentions. Bootstrap paired race-day blocks (2,000 repetitions seed 20261124; stratify year; sensitivity venue-day), report 95% intervals; no repeated test-driven tuning.

## 4. P8.0 preflight and identity

1. Verify pilot ZIP SHA `3737210f679348a54d714a737ec67351540037d140d098cbdc968617685ae2e3`, reproduce its 2025-only H2 counts 7009 eligible / 6810 scorable; A/AC/ACJ wins 1783/1791/1830, top1 top3 3892/3889/3937, winner in top3 3462/3489/3501. Exact algorithm from archived `recovery_pilot.py`, tolerance 1e-12 for features, exact rank/count parity (if output bytes differ due to writer metadata report both SHA). Do not overwrite pilot.
2. Audit canonical horse_key (hash horse_name + birth_date + sire_name, not official permanent ID). Missing keys, conflicting identities, date/age progression, same-day incompatible starts, split keys, name normalization variants, transfers, pedigree disagreement. Match only evidence available by cutoff. No fuzzy automatic merge; ambiguous keys quarantine historical linkage, keep target as UNKNOWN. Track key coverage and venue/year drift. Jockey/trainer provisional name+affiliation only for fixed ACJ reference; no new aux optimization. Do not use future observations to repair past features.
3. Separate pre target roster from historical valid result cohort. Target uses valid ENTRY scope only; freeze all target runners including unknowns; no target status filter until evaluator. Historical NORMAL/is_model_target, finish_count>1, valid finish_position and finish_time_seconds>0 (pilot parity); other status policies sensitivity separately. Cancellation/nonfinish/invalid observations excluded from history and logged. Evaluator reports NORMAL cohort with valid winning label, target without label excluded with counts; if predicted runner has null finish report strict intent-to-predict as miss plus separate settled/known-label metric (do not assume scratch vs DNF if indistinguishable). Dead heat: any rank1 winner, at most one hit per race; ties in scores deterministic horse_no asc, document sensitivity. Missing history means unknown, never zero. Top3 eligible if fewer than 3 scored horses: report incomplete separately.
4. Data audit dimensions: year/venue/surface/distance/conditions, source reconciliation 53 missing racelist races, runner/result keys, duplicates, valid time/margin/final3F/corner parse coverage, class/prize availability, count and source drift. Do not assert class comparability before audit.

## 5. P8A: base ability experiments

Define historical normalized finish p=1-(finish_position-1)/(finish_count-1) for valid observation. Frozen A: mean p over prior 180d, >=2 runs. Frozen AC: A + .25*n_course/(n_course+3)*(mean same venue/distance/surface p-A); ACJ: AC + .15*n_pair/(n_pair+20)*(prior 180d pair mean p-.5). Missing correction -> no adjustment; A unknown -> unscored. Pilot version remains 2025-only; multi-year expansion name `P8-A0/AC0/ACJ0` with same formula and cross-year history.

| ID | hypothesis / deterministic candidate |
|---|---|
| A1 | Recency: last 3/5/8 (within 365d), 90/180/365d mean, half-life 30/60/90d weighted mean on 365d, all min2; compare one factor at a time |
| A2 | Consistency: on A1 selected window, median, top2 mean (min2), last3 vs prior (min2 each), variance and days-since-last as diagnostics; reject best-only selection bias if unstable. Combine only after independent ablation |
| A3 | Class / opponent strength: venue×era×age-restriction class dictionary from race_type_name/conditions/race_name and prize_yen_1 as proxy only. Parse confidence/source; UNKNOWN if ambiguous. Do not assume C1 or prize equivalent nationally. Prior opponent base strength = mean of other runners' pre-race A using only their own earlier data; >=3 known opponents and >=50% coverage. Center/scale on prior observations only. Test additive correction to p (weight .1/.2) separately from class/proxy; no recursive feedback in first pass |
| A4 | Speed: observed finish_time_seconds vs earlier reference for same venue/surface/distance, prior 365d, median and robust MAD (min100 races, each race contributes winner time once; reference before historical race date). Standardized score higher=faster, clip [-3,3], map to [0,1] with .5+z/6; unavailable on zero MAD or insufficient support. Compare historical time deviation and within-race time-behind-winner in separate variants. Same-race result use only for historical observations. Test additive blend .15/.30 with base, no target time |
| A5 | Candidate integration: A1/A2 winner, A3 or A4 incremental improvement, then both only if isolated gain. Keep additive component decomposition. For zero/one-run horses compare abstain vs separate low-evidence A (one run shrinkage to prior neutral p=.5, k=3; zero-run unknown); no forced ranking of zero-run horses, report impact separately. |

All grids predeclared, staged (not full Cartesian), validation sees only a frozen shortlist from development. Class proxy mapping and speed reference version fixed before validation; no venue-specific coefficient hunting. A4 historically past going split optional in P8B, no target weather. A3/A4 features from prior date of *historical* event, not just target date. Reference fallback none initially; never compare raw seconds between different distances. No target class correction in A without testing; class transition belongs B. If lack of reliable labels for class/time, mark variant INFEASIBLE rather than invent.

## 6. P8B: course/condition fit and scenario

Use selected A* as base. Each B tested alone vs A*, then combine accepted effects, compare AC0 and A*. All residual estimates centered relative to baseline historical ability and shrink toward zero; missing or sparse -> no correction, not adverse evidence. Prior samples bounded (180/365d), exact cutoff.

| ID | feature / initial experiment |
|---|---|
| B1 | Same course fit: venue / distance-band / exact venue×distance×surface / direction. Distance bands initially <=1000,1001–1400,1401–1700,1701–2000,>2000m; compare exact vs band, not both stacked. Fit residual = mean subset p minus mean all p, shrink n/(n+k), k=3/10, weight .15/.25. Compare AC0 unchanged. Test transfer cases (new venue, distance up/down), no unsupported cross-venue equivalence |
| B2 | Class transition and speed fit: change from previous class to target local class (within venue/version only), historical performance residual by comparable class. For different venue use A3 opponent/speed comparison, unknown if not supported. Past condition-aware reference times (past going/season) compare against A4; target going branch RACE_DAY only. Fit based on prior 365d, min100 race references; no reference -> no adjustment |
| B3 | Draw and course bias: relative gate/horse_no position normalized by pre field_size; course-specific prior observed performance residual vs horse base, rolling 365d, min200 races, shrink group counts n/(n+100); inspect field-size strata, compare without bias term. Never use actual finish_count as target denominator |
| B4 | Pace/style: parse named historical corners, group/tie semantics and unmatched horse_no; audit coverage by venue×distance/year. Relative first available meaningful corner position, final-corner position, gain and prior final3F relative to comparable cohort; classify style by first-corner percentile <=1/3 front, >=2/3 rear, else middle (ties documented). Use latest 3–5 within 180d, min2 valid. Target expected field pressure = fraction front among known style runners, min 50% known and >=4 known; not actual target pace. Estimate prior course×style×pressure-bin residual (pressure low <.25, medium .25–.40, high >.40), min100 historical races and shrink n/(n+100); if parsing or support inadequate defer. Historical expected pressure also built strictly from earlier info. Test style-only vs interaction. No target result/corner/lap |
| B5 | Integration: A* + independently useful corrections (class, course, draw, pace). Compare additive ablations, no duplicate overlapping terms without explicit evidence, no venue-specific weights until sample support. Target RACE_DAY experimental branch only after ENTRY freeze and observation-time caveat |

B corrections from residuals scaled to A score; test .10/.20 weight unless B1 fixed grid. Document support and clipping before validation. Course/pace description from all years is descriptive only; cannot be used to derive predictions or select coefficients after opening confirmation period. B4 race-level historical pressure must be computed from past-only features of each entrant, not observed early-position shares of that race.

## 7. Metrics / decisions

Primary: top-ranked win rate on common eligible races, paired delta against current comparator; full-cohort intent-to-predict hit rate (abstentions count as no hit) and race/runner coverage as co-primary guard. Secondary: top1 3rd-or-better rate (not actual PLACE payout), winner in top3, top3 recall, race rank concordance on valid finishers, month/year/venue/course/class/field-size/history-count/transfer/missing breakdown. For top3 metrics also report same fixed >=3 scored support and all eligible races. Report hit counts, denominators, percentage-point differences, CI, tie/unknown counts. No probability calibration until probability model exists; no ROI or market inputs in P8.

Proposed predeclared promotion-to-P9 gate (research candidate, not production): all data/leakage/reproduction checks PASS; development and 2022–23 validation delta positive; locked 2024–25 paired top1 win delta >=0.3pp and 95% lower bound >0, top1 top3 and winner-in-top3 no worse than -0.5pp point delta; full-cohort intent-to-predict not worse and race coverage loss <=0.5pp and runner coverage loss <=1pp (common cohort and full cohort both reported); positive annual validation delta in both 2022/23 for candidate selection; flag material venue declines (>2pp on >=500 common races in confirmation) for review, no post-hoc routing. Thresholds design choices, not empirical findings. Select a single primary integrated candidate before confirmation, others diagnostic. If fail, retain simpler baseline, record HOLD/REJECT/INFEASIBLE, do not tune on confirmation. Research phase may complete with no promotion. Avoid choosing variants solely by top1 rate on reduced coverage. Store all attempts, including negative results; no silent deletions.

## 8. Leakage / reproducibility gates

Mandatory for each feature family: source allowlist and stage enforcement, forbidden column injection (popularity/payout/PENDING/target status) rejected; target/same-day/future history negative injection rejected or demonstrably excluded and counted; prefix/full future-addition invariance across each year boundary, several venues, sparse and missing cases; historical reference cutoff at historical date; year-boundary lookback continuity, deterministic ties and exact counts; isolated scoring reads frozen features only and evaluator reads frozen predictions + labels after SHA freeze; scoring unchanged when evaluator labels permuted; verify no training/normalization/identity future leakage. Test same-day results with extreme values, target results mutation, future identity correction and future append. Counts, max history date, cutoff, input IDs/SHA, version, exclusion and missing reasons per family per runner (or auditable linked lineage). Tolerance 1e-12 float, exact keys/ranks. Failure blocks downstream scoring, not a warning. Report monthly source as-of limitation.

## 9. Delivery / phase gates

| Step | Gate and artifact |
|---|---|
| P8.0 | pilot reproduction, input manifest, entity/key/coverage audit, leakage tests, experiment registry frozen |
| P8A.1 | A0/AC0/ACJ0 across development/validation, yearly/venue counts; A1/A2 ablation |
| P8A.2 | A3 class/opponent feasibility, A4 reference/time feasibility, isolated ablations |
| P8A.3 | A* candidate config + rejection ledger, validation predictions freeze |
| P8B.1 | B1/B2 course and class/condition experiments |
| P8B.2 | B3/B4 draw/pace experiments, parse audit, missingness |
| P8B.3 | B5 integration, freeze candidate configs, open retrospective 2024–25 confirmation once, report metrics and gate decision |
| P8.close | summary/model card, P9 input contract, code/config/tests + artifacts + readback |

Artifacts: versioned `input_manifest.json`, `entity_audit.json`, `experiment_registry.json`, `feature_dictionary.json`, `leakage_audit.json`, `feature_freeze.parquet`, `prediction_freeze.parquet` (all target keys incl unscored reason), `metrics_by_fold.csv`, `metrics_by_segment.csv`, `decision_ledger.csv`, `candidate_config.json`, `report.md`, `SHA256SUMS`. Version each run, no overwriting. Code/config/spec/test and summary in GitHub `local-horse-racing/`; private detailed outputs in Drive `/GPT/local-horse-racing/30_analysis/P8/<run_id>/`; compact portable bundle + handoff in Library `/地方競馬予想/P8/`. Native private connector only; no public uploads or raw data in Git. If Drive save blocked, retain private Library artifact with explicit status; do not mark complete until required saves and readback/hash parity verified. Git commit and main readback, Library readback; record code SHA/input/output hashes/runtime. Each experiment phase records progress and negative findings; do not rely on chat state. P9 receives selected A*/B* or simpler fallback and missingness/coverage flags, no P8 label or promotion implied until completed. P8 design only; next execution P8.0.

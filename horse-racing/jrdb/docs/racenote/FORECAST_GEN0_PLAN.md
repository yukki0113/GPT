# RaceNote Forecast Gen0 plan

Status: CURRENT RESEARCH PLAN / FORECAST LOGIC UNFROZEN
Last reviewed: 2026-10-03

> RaceNote extraction / evidence boundaries and the pre-result research lifecycle are fixed.
> Detailed Forecast decision logic is **not yet adopted**.
> `RaceNote-Forecast-Gen0.3` is an implemented research candidate, not the Gen0 default.
> `Gen0-G001` activation preparation is paused until a Forecast logic version is explicitly selected.

### Gen0-G001 preparation status — 2026-09-29

The fixed 50 PRIMARY + 20 RESERVE sample manifest, ledger registration, and
single-race artifact-only transport smoke are preserved as valid engineering
evidence. However, they were prepared before the project explicitly separated
"research infrastructure" from "adopted Forecast logic".

Gen0-G001 is therefore **PAUSED BEFORE ACTIVATION**. The next gate is Forecast
logic selection through blinded historical research, not a TRUE_FORWARD run of
Gen0.3. `forecast.current_generation` remains `Gen0-G000`.

Canonical status: `docs/racenote/GEN0_G001_ACTIVATION_STATUS.md`.


### Current Human-Context BTDAY prospective lane — 2026-10-04

The active historical logic-selection lane now uses
`RaceNote-Human-Context-Reader-0.4.5-candidate` on new unused BTDAYs.

Cohort boundaries are fixed by version. v0.4.5 intentionally inherits v0.4.4
prediction semantics while changing the execution contract.

v0.4.5 keeps full clean Reader evidence, race-model formation, four ordinary
mainline cases, independent ▲, hierarchy review and provisional-△2 Coverage
review. It does not retune SWAP semantics.

Execution changes:

- lossless semantic Reader chunking;
- compact model-authored Decision Core;
- immutable one-race checkpoints;
- resume from first missing race;
- deterministic audit materialization before strict Freeze.

Canonical logic:
`docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_4_5_CANDIDATE.md`

Canonical operating procedure:
`docs/racenote/BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md`

This remains a research-candidate change and does not promote the production
Forecast pointer.



### Forecast execution / research responsibility split

Current operation separates chat responsibilities:

- Forecast execution thread: prediction / Freeze / HTML / handoff only
- Research thread: result open / evaluation / logic adjustment

Canonical:
- `docs/racenote/FORECAST_GEN0_THREAD_ROLES_v0_1.md`
- `docs/racenote/FORECAST_EXECUTION_THREAD_BOOTSTRAP_v0_1.md`

### Forecast-axis calibration hold — 2026-09-29

The blind-day loop is temporarily paused.

Reason:
- v0.1 produced generic numeric-ranking forecasts;
- v0.2 improved trace observability but did not materially change the selection behavior;
- spending another ~2 clean days / ~50 races per wording adjustment would waste the finite 2026 pool.

Current:
- phase: `CALIBRATION_HOLD`
- logic: `RaceNote-Human-Context-Reader-0.3`
- teacher: `racenote/evidence/human_forecast_evidence_202301.md`
- calibration: `docs/racenote/FORECAST_AXIS_CALIBRATION_PROTOCOL_v0_1.md`

Rules:
- no new unused PACI day selection during hold;
- use 6–12 representative races from already-used / ineligible dates;
- calibration results are not performance evidence;
- resume two-day blind turns only after Research thread accepts the forecast axis.

### Current Backtest / TRUE_FORWARD research operating assets — 2026-09-29

The common operating contract is now:

- `docs/racenote/FORECAST_GEN0_RESEARCH_PROTOCOL_v0_1.md`
- `docs/racenote/FORECAST_GEN0_OUTPUT_CONTRACT_v0_1.md`
- `config/racenote_forecast_logic_current.json` — current logic pointer
- `schema/racenote_forecast_research_record_v0_3.json` — current calibration record schema
- `docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_3.md` — current human-context calibration logic
- `docs/racenote/FORECAST_DECISION_TRACE_CONTRACT_v0_1.md` — per-race reasoning summary contract
- `src/validate_racenote_forecast_decision_trace.py` — pre-Freeze trace validator

BTDAY-0001 remains frozen under `RaceNote-Baseline-Reader-0.1`.
The move to v0.2 is a pre-result observability fix, not result-based tuning.

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

## 1. Goal

RaceNote Forecast Gen0の目的は、固定ルールで印を機械生成することではなく、**RaceNoteの開催前evidenceをGPTが読み、比較し、予想し、その読み方を結果から改善する研究サイクル**を成立させることである。

評価対象は単なる的中率だけではない。

- どのevidenceを重く読んだか
- どのevidenceを読み落としたか
- 過大評価 / 過小評価は何だったか
- 相手比較で何を誤ったか
- 不確実性を適切に表現できたか
- Reader View / RaceNoteに不足情報があったか

をprediction時点の記録とpost-race結果から検証する。

## 2. One-race lifecycle

1Rについて必ず次の順序を守る。

```text
pre-race source resolve
  -> RaceNote validation
  -> GPT evidence reading
  -> horse-to-horse comparison
  -> prediction draft
  -> pre-result self-audit
  -> deterministic validation / hash
  -> immutable freeze
  -> Google Sheets readback
  -> result acquisition
  -> post-race evaluation
```

結果取得をprediction freezeおよびledger readbackより前へ置かない。

## 3. Prediction inputs

Gen0共通では、1 raceにつきresult-independent RaceNote evidenceを入力とする。
詳細なEvidence reading orderはまだ研究対象であり、Gen0.3の入力順を
current defaultとして固定しない。

Current research baselineは
`config/racenote_forecast_logic_current.json`
からresolveする。

Current baseline v0.2の読み方:

```text
RaceNote
  -> race context
  -> read every runner
  -> identify race thesis
  -> build candidate cluster
  -> explicit ◎ vs ○ comparison
  -> counter-evidence / downweighted evidence / reversal condition
  -> marks
  -> Decision Trace validation
  -> Freeze
```

Gen0.3の

```text
General Evidence
  -> All-Runner Synthesis
  -> Pairwise
  -> Scenario
  -> Base Forecast
  -> EdgeDB Performance
  -> Final Forecast
```

は比較用candidate固有pipelineであり、Gen0共通のmandatory input orderではない。

### Pre-Freeze allowed

RaceNote contract上許可されたas-of-safe pre-race evidence。
例:
- race condition / course context
- historical ability / suitability / recent-run content
- historical Trend
- historical RaceReview
- workout / stable / jockey / pedigree等のpre-race facts

candidate固有laneを使う場合は、そのcandidate contractに明記する。

### Pre-Freeze forbidden

- target result / payout
- final odds / final popularity
- current hidden JRDB consensus
- Edge Value / RL Value
- Training Edge
- target post-race review
- any target evaluation label

Current baseline v0.2はEdgeDB Performance overlayを必須にしない。

## 4. Initial factor set

`FSET-Gen0.1` は Gen0-G000 の初期研究factor setとして保持する。

Gen0.3 candidateでは、factor番号順ではなく次のEvidence lane順を試している。これは研究仮説であり、Gen0共通の固定reading orderではない。

General EvidenceからAll-Runner Synthesisへ入る直前に
`PredictionInterpretation-v0.1` を作る。
これはTrend / RR / Abilityのraw Evidenceを非加点で整理するpre-readであり、
順位・印・確率は決定しない。PairwiseはInterpretationを先に読み、
その後raw Evidence laneを再確認する。

その後 `All-Runner Synthesis v0.1` で全馬を一度に横比較し、
non-scoringのdraft orderと重点Pairwise境界を作る。
新規運用ではdraft orderをPairwiseへ直接手渡ししない。

```text
DATA_TREND
  -> RACEREVIEW
  -> ABILITY_ANCHOR
  -> relative comparison
```

したがってF01基礎能力を先頭だから最重要、と解釈してはならない。

2026-09-25時点で `General Evidence v0.1`、
`Pairwise Comparison v0.1`、`Scenario Robustness v0.1`、
`RaceNote-Forecast-Gen0.3` まで**研究候補として実装済み**。
これらを必須工程として採用するか、SLOW / MEDIUM / FASTを残すか、
EdgeDB Performanceをpre-Freezeで使うかを含め、詳細Forecast logicは
2026 PACI blinded historical backtestで比較して決める。

初期factor setは `FSET-Gen0.1` の10ファクター。

1. F01 基礎能力
2. F02 条件適性
3. F03 展開・位置取り
4. F04 調教・状態
5. F05 近走内容
6. F06 長期履歴・条件実績
7. F07 騎手・厩舎
8. F08 血統
9. F09 枠・条件統計
10. F10 事前市場情報

これは固定weightではない。

GPTはレースごとに重要度を変え、不要なfactorを軽視してよい。どのfactorを重視・軽視したかは予想内容とは別に研究メタデータとして記録する。

詳細は `FORECAST_GEN0_PREDICTION_CONTRACT_v0_1.md`。

## 5. Forecast record

各予想は結果取得前に、少なくとも次を記録する。

### Identification

- target date
- venue
- race_no
- race_key
- source version / semantic hash
- forecast generation version
- evaluation mode (`BLINDED_HISTORICAL / TRUE_FORWARD`)

### Race reading

- race shape summary
- expected pace / position picture
- important condition factors
- primary factor codes
- de-emphasized factor codes

### Horse comparison

全馬について:

- horse_no / horse_name
- GPT rank
- mark
- strengths
- risks
- evidence summary
- evidence conflicts
- comparison against nearby rivals
- factor codes

各馬を読むが、保存するのは監査用のreason summaryでありprivate chain-of-thoughtではない。

### Final prediction

- ◎ / ○ / ▲ / △等の相対順位
- axis horse
- confidence A / B / C
- concise reason for the axis
- alternatives / upset candidates where appropriate
- uncertainty summary
- race thesis
- 2–4 decisive factors with interpretation
- explicit ◎ vs ○ comparison
- strongest counter-case
- downweighted evidence
- reversal condition

confidenceは的中確率ではなく、**入力coverageとevidence整合性に対する予想時点の確信度**とする。

## 6. Pre-result self-audit

freeze前にGPT自身が予想を監査する。

最低限、次を確認する。

- 全馬を見たか
- レース条件を先に読んだか
- 単一indexへ引っ張られていないか
- 能力と展開を分けて評価したか
- 調教を過剰に上書き材料へしていないか
- 小母数実績を100%だからという理由で強く評価していないか
- missingをnegative signalへ変換していないか
- contradictory evidenceを消していないか
- 人気 / base oddsだけで順位を決めていないか
- 各馬を独立採点しただけでなく横比較したか
- ◎の負け筋を確認したか
- target result / final odds / post-race情報を見ていないか
- Decision Traceがrace-specificか
- ◎と○の直接比較が残っているか
- strongest counter / reversal conditionが具体的か
- Decision Trace validator PASSか

監査によって予想を修正した場合、Freezeするのは修正後の最終予想だけとする。

## 7. Freeze

prediction freezeはresult acquisitionより先に完了させる。

freezeでは最低限:

- prediction body
- input identity / semantic hash
- generation version
- factor set version
- created_at
- pre-race guard status
- result visibility status
- prediction hash
- frozen_at

を固定する。

`src/racenote_forecast_gen0_3.py` はGen0.3 candidateのsource-chain / probability / mark / Edge Performance / freeze境界をdeterministicに検証する。Gen0共通で再利用すべきなのは、禁止情報検査・provenance・hash・immutable Freeze等の検証インフラであり、Gen0.3固有のmark/probability決定規則ではない。

禁止result field、pre-race guard不成立、結果visible、mark/axis内部不整合、hash不整合はfail closedとする。

既存TRUE_FORWARD資産のhash / provenance / immutable recordの考え方は再利用するが、旧v1.1-Pの印決定ロジック自体をGen0へ持ち込まない。

## 8. Google Sheets ledger

継続台帳はネイティブGoogle Sheet `RaceNote Forecast Gen0 検証台帳`。

正本config:

`config/racenote_forecast_gen0_ledger_v0_3.json`

Google SheetsはChatGPTのDrive / Sheets connectorから直接read / writeする。RaceNote sourceへGoogle API clientやcredentialを持ち込まない。

pre-resultでは:

- `予想Freeze`
- `馬別評価`
- `ファクター使用`
- `Freeze監査`

を同一transactionで記帳する。

post-resultでは:

- `結果_馬別`
- `振返り`
- `ファクター検証`
- `Freeze監査`

を更新する。

詳細は `FORECAST_GEN0_LEDGER_CONTRACT_v0_1.md`。

## 9. Post-race evaluation

結果取得後は「当たった / 外れた」だけで終わらせない。

`src/racenote_forecast_gen0_evaluation.py` は結果identity、freeze-before-resultを検証し、◎着順・winner mark・印内捕捉等の客観指標を作る。

### Outcome

- ◎着順
- ◎勝利
- winnerをどこまで評価できていたか
- 上位候補の順位整合性
- 印内の上位3着捕捉
- 必要に応じて馬券評価。ただしprediction evaluationとは分ける

### Reading audit

- ability reading
- condition reading
- pace / position reading
- suitability reading
- recent-run interpretation
- long-history interpretation
- context-stat interpretation
- uncertainty handling

について、予想時点の根拠と結果後の事実を比較する。

### Factor audit

予想時に記録したfactor usageへ対し:

- HELPFUL
- NEUTRAL
- MISLEADING
- UNRESOLVED

および:

- OVER
- UNDER
- APPROPRIATE
- NA

を記録する。

結果を知った後の後付け説明でprediction recordを書き換えない。



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

## 10. Improvement unit

原則として**約50Rを1改善単位**とする。

初期generation:

- `Gen0-G000`
- `RaceNote-Forecast-Gen0.1`
- `FSET-Gen0.1`
- initial mode: `BLINDED_HISTORICAL`
- target: 50R

1Rごとの結果で即座にweight・ルール・reading orderを変更しない。

50R程度のまとまりで、少なくとも次を集計する。

- ◎成績
- 印別成績
- confidence別成績
- favorite / mid-price / longshot等の市場帯別傾向
- surface / distance / class別傾向
- factor別 `HELPFUL / MISLEADING`
- factor別 `OVER / UNDER`
- reading-error category件数
- recurring overvaluation / undervaluation
- missing-data起因の失敗
- Reader View不足項目

50Rは絶対値ではなく、過学習を避けてまとまった傾向を見るための初期運用単位である。

## 11. Change discipline

改善案は次の3種類へ分ける。

### A. Reading guidance change

GPTが既存情報をどう読むかの改善。

例:

- pace interpretationの順番
- small sampleの扱い
- contradictory evidenceの残し方

### B. Input / RaceNote change

必要なevidence自体が不足している場合のdata contract改善。

RaceNote authoritative factsを変える場合は、prediction都合だけで意味を捏造せずsource / provenanceを明確にする。

### C. Model / rule experiment

固定weight、score、gate等を導入する実験。

これはGen0の自然言語比較とは分け、独立version・blind test・forward testで評価する。

旧方式の成績が良かったことだけを理由にcurrent Gen0をv1.1-Pへ戻さない。

## 12. Relationship with EdgeDB

EdgeDBは有用なhistorical evidence sourceになり得るが、Gen0 core factor setでは旧v1.1-PのようにEdge polarityだけで機械的に軸を入れ替えない。

Edgeを使う別実験では:

- Performance / Valueを区別する
- CONFIRMED / SUGGESTIVEを区別する
- overlapを安易に加算しない
- sample / applicability / current-matchを確認する
- 他のRaceNote evidenceと横比較する

という既存EdgeDB contractを守る。

## 13. Relationship with external sources

Eval、keibailuka、その他外部sourceはRaceNote単独Gen0へ暗黙に混ぜない。

併用研究を行う場合はsource別に記録し、RaceNote-only predictionとの比較が可能な状態を保つ。

## 14. Initial acceptance target

Gen0初期段階の成功条件は「高い的中率を宣言できること」ではない。

まず次を安定して満たすことを優先する。

- pre-race onlyを守れる
- 同じRaceNote evidenceから一貫した比較理由を残せる
- predictionとpost-race解説を混同しない
- 予想根拠を後から監査できる
- Google Sheetsへtransaction単位で記帳できる
- factor usageとpost-race factor reviewをjoinできる
- 一定R単位で失敗パターンを集約できる
- 改善前後のversion差を追跡できる

この基盤が成立してから、accuracy / ranking quality / betting valueの改善へ進む。

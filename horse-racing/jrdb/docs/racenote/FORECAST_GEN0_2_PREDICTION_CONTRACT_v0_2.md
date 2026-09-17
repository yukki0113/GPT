# RaceNote Forecast Gen0.2 Prediction Contract v0.2

Status: IMPLEMENTED / NOT YET ACTIVATED
Date: 2026-09-17

## 1. Scope

Gen0-G000 / RaceNote-Forecast-Gen0.1 はimmutable historical generationとして維持する。
Gen0.2は別versionとして実装し、次generationでのみ使用する。

Planned identity:

- generation: `Gen0-G001`
- forecast version: `RaceNote-Forecast-Gen0.2`
- factor set: `FSET-Gen0.2`
- input firewall: `Gen0.2-Firewall-0.1`

## 2. Forecast lifecycle

```text
RaceNote v1.0 authoritative bundle
 -> Gen0.2 input firewall
 -> INDEPENDENT view only
 -> all-runner reading
 -> p_win_base / p_top2_base / p_top3_base
 -> base snapshot hash
 -> EdgeDB performance signal only
 -> p_win_final / p_top2_final / p_top3_final
 -> marks
 -> forecast hash / immutable Freeze
 -> JRDB consensus view opened
 -> market view opened / fair odds / raw EV
 -> optional betting-plan freeze
 -> newspaper consumer may display TE separately
 -> result acquisition
```

## 3. Independent forecast firewall

Before forecast Freeze, GPT may not see current-entry JRDB consensus or market containers.

Independent view contains:

- race conditions and race-level historical trends
- basic horse identity / jockey / trainer / carried weight
- historical race facts and comments
- prior-run IDM as historical performance summary
- raw main-workout facts and limited factual preparation summaries
- rotation/rest facts
- historical profile and as-of-safe sire/jockey/frame statistics
- coverage / missing-information metadata

The independent view excludes:

- current-entry IDM
- current-entry total/composite index
- current JRDB marks / ratings
- current JRDB pace indices/ranks and forecast finish order
- processed current training/condition indices used as JRDB consensus
- current market/base odds and ranks
- historical final odds/popularity from independent history display
- Training Edge

Implementation:

`src/racenote_gen0_2_input_firewall.py`

The firewall emits:

- `independent_view.json`
- `jrdb_consensus_view.json`
- `market_view.json`
- `firewall_manifest.json`

Each view has deterministic semantic SHA-256 provenance.

## 4. Prediction factors

Prediction factor set:

- F01 過去パフォーマンス・基礎能力
- F02 今回条件適性
- F03 独立展開・位置取り
- F04 調教・状態 raw evidence
- F05 近走内容・trip quality
- F06 長期履歴・条件実績
- F07 騎手・厩舎
- F08 血統
- F09 枠・条件統計
- E01 EdgeDB performance signal

Removed from prediction-factor namespace:

- old F10 market information

Separate namespaces:

- C01 JRDB consensus: post-forecast comparison only
- M01 market price: value/betting only
- M02 EdgeDB value signal: value/betting only
- T01 Training Edge: newspaper display / human purchase overlay only

## 5. Probability output

Every runner must receive both base and final probability snapshots:

- `p_win_base`
- `p_top2_base`
- `p_top3_base`
- `p_win_final`
- `p_top2_final`
- `p_top3_final`

Rules:

- each probability in [0,1]
- per horse: p_win <= p_top2 <= p_top3
- sum p_win approximately 1
- sum p_top2 approximately min(2, runner count)
- sum p_top3 approximately min(3, runner count)
- base and final ranks are each contiguous over all runners
- final-rank 1 is ◎
- ◎ must have maximum p_win_final

Initial Gen0.2 probabilities are explicitly uncalibrated model estimates. Result-phase evaluation must include calibration quality, Brier Score and Log Loss before treating small EV differences as reliable.

## 6. EdgeDB

EdgeDB is a proprietary RaceNote overlay, not the base ability model.

Forecast-visible EdgeDB evidence is limited to canonical as-of-safe `performance_signal` information.

Required provenance:

- status: USED / NO_MATCH / UNAVAILABLE
- matcher version when USED
- catalog reference/hash when USED
- `asof_status=PASS` when EdgeDB is evaluated
- `performance_only=true`
- `value_signal_visibility_status=HIDDEN_FROM_FORECAST`

Per runner, preserve:

- matched Edge IDs
- family list
- performance-signal summary
- adjustment direction/reason
- base rank / final rank
- base/final probabilities
- whether axis changed due to EdgeDB

Do not restore legacy deterministic Edge rules:

- no `0.02 * tier` fixed score adjustment
- no Good-gap 0.04 axis gate
- no automatic axis promotion from polarity
- no top-five-only Edge application

Same-family overlap must not be treated as independent votes.

For blinded historical work, EdgeDB may be used only where its evidence is proven as-of-safe for the target race. Otherwise set `edge_source.status=UNAVAILABLE` and leave base/final probability unchanged unless another as-of-safe performance overlay exists.

## 7. Training Edge

Training Edge is not a Gen0.2 forecast input.

The forecast payload must assert:

`training_edge_forecast_status = NOT_USED`

TE may be displayed in the newspaper/PWA next to RaceNote and JRDB, and the human purchaser may use it when actually betting. Such Human Overlay decisions are not part of the RaceNote forecast record and must be evaluated separately if logged.

## 8. Freeze boundary

The RaceNote forecast must be frozen before either current JRDB consensus or market views are opened.

Freeze includes:

- independent-view hash
- source bundle hash
- base snapshot hash
- EdgeDB provenance
- all-runner base/final probabilities and ranks
- marks
- factor usage
- prediction hash
- frozen_at

`src/racenote_forecast_gen0_2.py` provides validation, deterministic hashing, freeze, audit and ledger projection.

## 9. JRDB consensus comparison

After forecast Freeze only, open `JRDB_CONSENSUS` view and record:

- RaceNote rank / mark
- JRDB current IDM
- JRDB total/composite index
- JRDB total / IDM / training marks
- JRDB forecast finish rank where present
- comparison timestamp and consensus-view hash

This step must never mutate RaceNote probabilities or marks.

## 10. Market/value layer

After forecast Freeze only, open the market view.

For win market:

`fair_win_odds = 1 / p_win_final`

`win_ev_raw = p_win_final * market_win_odds - 1`

Raw EV is a research field while Gen0.2 probabilities are uncalibrated. No production buy threshold is authorized by this contract.

Final odds/result/payout remain forbidden before result phase.

## 11. Betting policy separation

Forecast version and betting policy version are separate.

Initial Gen0.2 may construct/research win/place plans from marginal probabilities. Quinella/trio exact EV must not be fabricated from marginal probabilities alone. Combination bets may be logged with `EV_NOT_MODELED` until a coherent joint-ranking probability model is separately versioned and validated.

## 12. Ledger

Gen0.2 reuses the immutable Gen0 ledger and adds:

- `確率評価`
- `EdgeDB補正`
- `JRDB照合`
- `市場Snapshot`
- `馬券Plan`

Legacy Gen0.1 tabs/rows remain unchanged.

Config:

`config/racenote_forecast_gen0_ledger_v0_2.json`

## 13. Activation rule

Implementation availability does not activate Gen0.2 automatically.

Activation requires:

1. code/schema/tests present on main;
2. ledger tabs present;
3. next-generation sampling manifest fixed before prediction;
4. generation metadata explicitly set to Gen0-G001 / Gen0.2;
5. no Gen0-G000 frozen row is rewritten.

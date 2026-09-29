# RaceNote Forecast Gen0 Research Protocol v0.1

Status: **CURRENT**
Date: 2026-09-29

## 1. Purpose

RaceNoteを入力として、詳細Forecast logicをバックテストで探索し、
採用後は同じprediction / Freeze / evaluation contractのまま
TRUE_FORWARDへ移行するための共通研究プロトコル。

この文書は「どの馬を◎にするか」を決める予想ロジックではない。
予想ロジックを公平に比較・改善するための**固定実験枠**を定義する。

## 2. Fixed vs unfrozen

### Fixed

- RaceNoteはfacts / evidence / provenance layerであり、RaceNote自身は印を決めない。
- historical evidenceは必ず `race_date < target_date`。
- target result / payout / final odds / final popularity / prohibited current consensusはFreeze前に見ない。
- 1レースの予想は独立させる。
- predictionはresult open前にimmutable Freezeする。
- Freeze後に結果を開いてもpredictionを書き換えない。
- バックテストとTRUE_FORWARDは同じ保存形式を使う。
- logicを変更したらlogic_versionを変える。
- 一つの研究ターンの途中ではlogicを変更しない。

### Unfrozen

- Trend / RaceReview / Abilityのreading priority
- evidence conflictの解消方法
- Synthesis / Pairwise / Scenarioを使うか
- EdgeDB Performanceを使うか
- confidence / probability policy
- ◎○▲△の詳細決定方法
- numeric score / weightの有無
- prompt wording

`RaceNote-Forecast-Gen0.3` はこれらの一候補実装であり、採用済みdefaultではない。

## 2.1 Initial baseline

The first historical turn uses:

- logic version: `RaceNote-Baseline-Reader-0.1`
- contract: `docs/racenote/FORECAST_GEN0_BASELINE_READER_v0_1.md`
- config: `config/racenote_forecast_logic_baseline_v0_1.json`

This baseline deliberately avoids fixed evidence priorities, scores, mandatory
Pairwise/Scenario, and Gen0.3-specific reading rules. It exists to provide a
stable starting point for observed improvements.

## 3. One turn

Historical backtestの標準研究単位は **未使用eligibleな2開催日**。

```text
unused eligible PACI days
  -> random PICK 2 days
  -> target days frozen
  -> same logic_version for every target race
  -> race-by-race prediction / Freeze
  -> both days complete
  -> result open
  -> deterministic metrics + qualitative review
  -> decide one bounded logic change
  -> next turn
```

通常は2日で約48–72Rを見込む。
実レース数がこの範囲外でも、抽選後に都合で日付を差し替えない。

### Turn invariants

- 1 turn内は同一logic_version。
- 1 race = 1 independent forecast callをbaselineとする。
- 12R/36Rを一つのreasoning callでまとめて印決定しない。
- source/validation failure raceは `TECHNICAL_SKIP` として残す。
- 結果を見てから同turnの別レースlogicを変更しない。
- turn終了後の変更は原則1テーマに限定する。

Each new two-day turn is a walk-forward blind check of the logic version that
exists before its results are opened. After result open, that same turn becomes
development evidence for the next version. Separate historical holdout blocks
may be reserved later, but are not required for the normal iteration cadence.

## 4. Day selection

Canonical state:

`config/racenote_backtest_day_pool_2026.json`

Picker:

`src/racenote_backtest_day_picker.py`

Default:

```bash
python src/racenote_backtest_day_picker.py pick \
  --state config/racenote_backtest_day_pool_2026.json \
  -n 2
```

PICKされた日はusedとなり、selection_id / seed / used_atを保持する。

新しいPACI開催日がDriveへ追加されたらinventoryをsyncし、
既存used stateを保持したまま新しい日だけunused候補へ追加する。

既にproject内でtarget resultを開いている日付はclean blind turnから除外できる。
除外情報はpool stateのeligibility / exclusion_reasonで管理する。

## 5. One-race prediction contract

candidate logicに依存せず最低限保存する。

### Identity

- target_date
- venue
- race_no
- race_key
- race_name
- surface / distance / class where available
- evaluation_mode: `BLINDED_HISTORICAL` or `TRUE_FORWARD`
- turn_id
- logic_version
- RaceNote source identity / semantic hash

### Prediction

最低限:

- ordered marks
- ◎ horse_no / horse_name
- ○ horse where used
- ▲ horse where used
- △ horses where used
- concise axis comment
- concise uncertainty / concern
- optional full-field order

印の意味そのものはcandidate logicでversion管理する。
ただし◎は共通presentation上、**「今回、自分なら一番買いたい馬」**を表す。

### Audit metadata

- created_at
- frozen_at
- prediction_hash
- pre_result_guard
- result_visible = false at Freeze
- candidate-specific trace references

詳細private reasoningは保存しない。
再検証可能な短いevidence summary / decision traceを保存する。

## 6. Internal canonical record

GPT / analysis向けの正本はstructured JSON / JSONL。

目的:

- candidate間比較
- result join
- error taxonomy集計
- logic version差分
- turn単位集計
- later TRUE_FORWARD reuse

Human-readable HTMLはこの正本から生成し、HTMLから予想を再構築しない。

Canonical common schema:

`schema/racenote_forecast_research_record_v0_1.json`

## 7. User-facing forecast delivery

あなた向け標準提出は **1日1HTML**。

例:

- `forecast_20260104.html`
- `forecast_20260105.html`

トップには会場別の一覧を置く。

| R | Race | ◎ | ○ | ▲ | △ | Comment |
|---:|---|---|---|---|---|---|

表示原則:

- 日付 → 会場 → R順で一望できる。
- 一覧の主役は印と短評。
- ◎は馬番 + 馬名を必ず表示。
- コメントは原則50–100字程度の短文。
- 必要なら各Rの下に◎の懸念点を短く表示。
- 内部evidence dumpや長いchain-of-thoughtは載せない。
- HTMLはpredictionのpresentationであり、印を再計算しない。

Canonical output contract:

`docs/racenote/FORECAST_GEN0_OUTPUT_CONTRACT_v0_1.md`

## 8. Turn review

2日すべてFreeze後に結果を開き、turn reviewを作る。

User-facing:
- `review_<turn_id>.html`

Internal:
- structured metrics JSON
- per-race evaluation JSONL

最低限見る指標:

### Axis
- ◎ win
- ◎ top2
- ◎ top3

### Candidate-set
- winner forecast rank
- winner in top3
- winner in top5
- actual podium in forecast top5
- top3 set overlap

### Full-order when available
- Spearman
- mean absolute rank error

### Error taxonomy
- DATA_TREND_OVERREAD / UNDERREAD
- RACEREVIEW_OVERREAD / UNDERREAD
- ABILITY_OVERREAD / UNDERREAD
- PAIRWISE_REVERSAL_ERROR
- SCENARIO_ASSUMPTION_ERROR
- CANDIDATE_CLUSTER_OK_AXIS_WRONG
- MISSING_EVIDENCE
- TECHNICAL_SKIP
- UNRESOLVED

candidateで使っていないlaneのerror tagは付けない。

## 9. Logic adjustment

turn review後、次turn前にだけlogicを変更できる。

変更は原則1テーマ。

良い例:
- mixed Trendを決定打にしすぎない
- candidate clusterから◎を選ぶ比較方法を変更
- recent-run contentをclass context込みで読む

避ける:
- Trend + Scenario + marks + probabilityを同時に全面改訂
- ROIだけを見てForecast readingを直接最適化
- 1Rの失敗だけで即変更

変更内容は旧versionを上書きせず新logic_versionとして残す。

## 10. TRUE_FORWARD transition

採用Forecast logicが決まったら、historical laneと同じcommon record /
human HTML / Freeze contractをTRUE_FORWARDへ持ち上げる。

変わるのは主に:

- evaluation_mode = `TRUE_FORWARD`
- target日は未来/未結果
- historical result-open stageは実レース終了後

変えない:

- RaceNote input boundary
- forbidden pre-Freeze information
- one-race independence
- immutable Freeze
- output schema
- presentation contract
- post-race evaluation shape

Gen0-G001等のactivation generationは、採用logic_version決定後に改めて定義する。

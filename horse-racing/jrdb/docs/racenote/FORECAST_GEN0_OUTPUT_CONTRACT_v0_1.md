# RaceNote Forecast Gen0 Output Contract v0.1

Status: **CURRENT**
Date: 2026-09-29

## 1. Two outputs, one prediction

Forecastは二層で保存する。

1. **Canonical structured record** — GPT / audit / evaluation向け
2. **Human HTML report** — ユーザー閲覧向け

両者は同一Freeze済みpredictionを表現する。
HTML側で印・順位・コメント根拠を再計算しない。

## 2. Canonical structured record

Current schema is resolved from `config/racenote_forecast_logic_current.json`.

Current at 2026-09-29:

`schema/racenote_forecast_research_record_v0_3_1.json`

Historical v0.1 / v0.2 / v0.3 records remain immutable under the schemas used
when they were frozen. Do not rewrite older turns into the current schema.

1 race = 1 recordを基本とする。

最低限:
- race identity
- evaluation mode / turn / logic version
- source identity
- marks
- axis
- short human-facing comments
- optional full-field order
- structured `decision_trace`
- audit / freeze metadata

Current Human-Context v0.3.1 trace includes:
- race_model / primary_question
- 3–5 candidate cases
- explicit ◎ vs ○ / ◎ vs ▲ comparison
- strongest counter-case
- reversal condition
- RRDB review trace (`rrdb_evidence`)
- human forecast principle references

Canonical trace contract:
`docs/racenote/FORECAST_DECISION_TRACE_CONTRACT_v0_1.md`

Human-facing comments may stay compact; they are not a substitute for the
canonical trace.

## 3. Daily human HTML

Filename:

`forecast_YYYYMMDD.html`

### Header

- date
- evaluation mode
- turn_id
- logic_version
- generated/frozen status

### Venue sections

会場ごとにR順の一覧表。

Required columns:

| column | content |
|---|---|
| R | race number |
| Race | race name + short condition |
| ◎ | horse no + horse name |
| ○ | horse no + horse name |
| ▲ | horse no + horse name |
| △ | compact horse list |
| Comment | concise axis reason |

Optional:
- Concern
- confidence label if candidate defines one

### Readability rules

- 印を最優先で視認できる。
- 1画面/スクロールで多数Rを比較しやすい。
- コメントは原則50–100字。
- evidence IDや内部codeは通常表示しない。
- missingは空欄ではなく必要に応じて `—`。
- technical skipは明示する。
- race detailを追加する場合も一覧を先頭に維持する。

## 4. Turn review HTML

Filename:

`review_<turn_id>.html`

表示:
- 対象2日
- logic_version
- race count / technical skips
- ◎ win/top2/top3
- winner top3/top5 coverage
- full-order metrics if available
- recurring error categories
- representative good/bad decisions
- next-turn change: exactly what is changed / unchanged

Betting ROIを載せる場合はForecast qualityと別sectionにする。

## 5. Immutability

Forecast HTMLはFreeze済みrecordから生成する。
結果開封後にprediction-side HTMLを書き換えない。

結果を重ねて見せる場合は別review HTMLを作る。


## 6. Turn handoff

Forecast execution threadは結果を開かず、turn終了時に:

- `turn_handoff_<turn_id>.json`
- canonical prediction records
- daily forecast HTML

をResearch threadへ渡す。

Schema:
`schema/racenote_forecast_turn_handoff_v0_1.json`

handoffは `result_opened = false` を必須とする。

Research threadはhandoff受領後にresult open / reviewを行う。


## 7. Freeze quality gate

For current records, before Freeze run:

`src/validate_racenote_forecast_human_context.py`

The current v0.3.1 gate also requires RRDB to be explicitly reviewed. RRDB may
be non-decisive, but when it is not used the trace must record why.

Freeze is invalid unless the current validator PASSes.

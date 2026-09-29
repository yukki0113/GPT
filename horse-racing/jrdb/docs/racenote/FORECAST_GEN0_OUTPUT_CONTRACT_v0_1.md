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

Schema:

`schema/racenote_forecast_research_record_v0_1.json`

1 race = 1 recordを基本とする。

最低限:
- race identity
- evaluation mode / turn / logic version
- source identity
- marks
- axis
- short comments
- optional full-field order
- audit / freeze metadata

Candidate固有の詳細traceは `candidate_trace` へ追加してよい。
common fieldの意味はcandidateごとに変えない。

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

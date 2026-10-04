# RaceNote Forecast Execution Thread Bootstrap v0.1

このスレッドは **RaceNote Forecast予想実行専用** として運用する。

## Bootstrap

GitHub `yukki0113/GPT` main の最新状態から、まず以下を確認する。

1. `horse-racing/jrdb/docs/racenote/FORECAST_GEN0_THREAD_ROLES_v0_1.md`
2. `horse-racing/jrdb/docs/racenote/FORECAST_GEN0_RESEARCH_PROTOCOL_v0_1.md`
3. `horse-racing/jrdb/docs/racenote/FORECAST_GEN0_OUTPUT_CONTRACT_v0_1.md`
4. `horse-racing/jrdb/config/racenote_forecast_logic_current.json`
5. BTDAY prospectiveでは `prospective_research_candidate` が示す logic contract / Decision Core schema / record schema / runbook
6. production/current forecastでは `current_logic_version` が示す contract / config / schema
7. current pointerが示す Freeze validator
8. `horse-racing/jrdb/config/racenote_backtest_day_pool_2026.json`
9. `horse-racing/jrdb/src/racenote_backtest_day_picker.py`

以後、会話内の古い説明よりlatest mainのcurrent assetsを優先する。

## Role

このスレッドの役割は **pre-result prediction executionのみ**。

- current phase確認
- `CALIBRATION_HOLD` 中は新しいunused eligible日をPICKしない
- calibrationでは既使用 / ineligible日からResearch thread指定の6–12Rだけを使う
- PACIからRaceNote準備
- Analysis/P1/P2 history enrichment
- RRDB formal enrichmentを実施
  - RaceReviewDB CURRENT
  - frozen Next-Watch rules
  - `racenote_rrdb_enrichment.py`
- RaceNote validation / firewall確認
- current logic_versionを全対象Rで固定
- 1 race = 1 independent forecast
- canonical research record保存
- current logicが要求するrace-specific trace作成
- human forecast teacher evidenceを必ず読む
- RaceNoteに`racereview`がある場合は全馬について確認する
- schema v0.3.1では`rrdb_evidence` traceを必ず残す
- RRDBを使わなかった場合も理由を残す
- current validator PASS
- immutable Freeze
- 日別forecast HTML生成
- turn handoff manifest生成
- Freeze済み成果物をユーザーへ提出

## Do not do

このスレッドではtarget resultを開かない。

禁止:

- 着順 / payout / final odds / final popularityの取得
- result join
- post-race評価
- ロジック調整
- turn途中のprompt / reading policy変更
- 結果を知った後の予想修正
- current logicに書かれていない別candidate logicの混入

予想中に見つけた課題は短い `execution_observations` として残し、
その場でlogicへ反映しない。

テンプレート短評へ馬名・数値だけを差し込むことは禁止。
特にcurrent v0.3では:
- 単一の総合値 / Ability / 調教等による機械順位を作らない
- 馬を選ぶ前にrace_modelを作る
- 3–5頭のcandidate caseを比較する
- human forecast evidenceのprincipleを1–3件明示する
- marks確定後にのみfull-field orderを作ってよい

## Output

各日:
- canonical prediction JSON / JSONL
- `forecast_YYYYMMDD.html`

turn全体:
- `turn_handoff_<turn_id>.json`

handoffには最低限:
- turn_id
- selected dates
- logic_version
- target/source identities
- total races
- frozen races
- technical skips
- prediction hashes / record locations
- HTML locations
- execution_observations
- `result_opened = false`

を含める。

全usable raceのFreezeとhandoff作成が終わったら停止し、
「結果確認・評価・ロジック調整は研究スレッドへ渡してください」と報告する。

## Current logic resolution

Never infer the BTDAY logic version from conversation history.

Read latest:
`config/racenote_forecast_logic_current.json`.

For BTDAY prospective research use only:
`prospective_research_candidate`.

For production/current forecast use:
`current_logic_version`.

Current BTDAY prospective at 2026-10-04:
`RaceNote-Human-Context-Reader-0.4.6-candidate`.

For v0.4.6, read the candidate contract and prospective runbook as one
self-contained operating context. Do not reconstruct the workflow by stacking
v0.4.4/v0.4.5 procedures underneath it.

Normal v0.4.6 execution:

```text
clean Reader
-> continuous prediction for one venue
-> one immutable venue batch save
-> automatically continue
-> bind complete day
-> Freeze / Validator / archive
```

The venue batch is only a recovery point. Saving it is never by itself a reason
to stop or ask the user for a continuation instruction.

If execution is genuinely interrupted, resume from the first unsaved venue
listed in the batch manifest and do not re-author completed venues.

The production pointer remains separate and unchanged unless explicitly
promoted by the research process.


## RRDB normal execution

Current normal RRDB sources:

- RRDB CURRENT stable file ID:
  `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`
- frozen Next-Watch rule artifact Drive file ID:
  `1AzhPgqr8GXei4opzbI8gD7nb4-5qZ3Zr`

Do not reimplement S/A grading in the execution thread.
Use repository enrichment / shared grading code.

If RRDB source resolution fails, record it as a technical evidence-source
failure. Do not silently replace it with an empty RRDB block and continue as if
RRDB had been reviewed.

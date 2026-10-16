# RaceNote Forecast Execution Thread Bootstrap v0.1

Status: CURRENT — v0.5.4 authored-prose r3 (2026-10-16)

このスレッドはRaceNoteの **pre-result prediction execution専用** とする。

## 1. Latest main / pointer interpretation

開始時は最新 `main` の `README.md`、`.gpt/HANDOFF.md`、`.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md`、および `docs/racenote/README.md` を確認する。

`config/racenote_forecast_logic_current.json` のポインタは用途別に分離する。

- `current_logic_version`: 別管理のproduction pointer。新規candidate予想を選ぶフィールドではない。
- `prospective_research_candidate`: 新規clean-blind candidate予想の入口。

新規予想では `prospective_research_candidate.logic_contract` と `runbook` を一組として読み、現在の contract revision を確認する。2026-10-16時点の新規clean-blind入口は v0.5.4 r3。過去versionの手順を混ぜない。歴史再現を明示された場合だけ対象versionのfrozen contractを使う。

## 2. Current candidate route

- Logic: `RaceNote-Human-Context-Reader-0.5.4-candidate`
- Contract revision: `v054-authored-prose-r3`
- Logic contract: `FORECAST_HUMAN_CONTEXT_READER_v0_5_4_CANDIDATE.md`
- Operation: `RACENOTE_V054_SINGLE_DAY_RUNBOOK_v0_1.md`
- Predecessor / historical reproduction: v0.5.3 r2
- Reader-facing prose: model-authored per race; no programmatic fallback

対象日指定またはBTDAY抽選後、source mode（2026 PACI / accepted Historical Warehouse）を解決し、canonical入力からDAY PREP、market-blind forecast_prep、sealed v0.5.4 Reader/sessionまで構築する。必要な依存が現runtimeに無い場合はcanonical pipelineを実行可能な環境へrouteし、代替Reader・暫定Freezeを作らない。

```text
source resolve / pre-race canonical input
  -> day prep + forecast prep
  -> SEALED v0.5.4 r3 Reader (READY_FOR_V054_AUTHORING)
  -> contract/schema preflight
  -> complete-Reader model authoring in 3-4R chunks
  -> full-card schema/quality preflight
  -> venue immutable save
  -> FROZEN_CLEAN_BLIND
  -> verify
  -> downstream publication; results only after Freeze/Verify
```

BTDAY予約、PACI / Warehouse準備、全会場の予想、Freeze/Verifyは同一予想依頼の内部工程である。会場保存後に確認待ちで止まらない。過去version用workflowをv0.5.4へ無審査で複製しない。

## 3. v0.5.4 r3 model judgment

Readerの全馬を読み、固定weightではなくレース全体の展開・能力・適性・状態・再現性・履歴を横比較する。

1. race modelを決める。
2. 順序付きordinary fiveを先に保護する。
3. ordinary five内から勝ち切る筋を重視して◎・○を確定する（`WIN_FIRST_NOT_PLACE_FIRST`）。
4. ordinary five外から非対称の勝ち筋を持つchallengerを1頭選ぶ（6頭以上）。
5. ◎○を除くordinary fiveの最低順位馬だけと比較する。`KEEP_ORDINARY_FIVE`が原則。route diversityはADMIT理由にならず、直接的なReader証拠で明確に競争力があるときだけ`ADMIT_CHALLENGER`。
6. Decision Coreを一度記録し、読者向けには自然な短評へ翻訳する。

Decision Coreの`ranking_reason`は◎と○の比較だけ、`boundary_review.reason`は固定境界との比較だけに用いる。既読Readerにない具体的事実を創作しない。候補選びを二度やり直さない。

## 4. Save / Freeze / recovery

正式な保存先は `<output-root>/v054/incoming/<venue>.json`、復旧点はmodel-authored 3–4R chunk checkpointおよびv0.5.4 `save` 済み会場。

T2開始時に active validator / persisted schema / authoring quality guard を一度確認する。全chunk執筆後、最初のActions Freezeを投げる前に全レースへ同じschema/quality条件のpreflightを一括適用し、違反をFreeze前に解消する。schemaやqualityをActions実行後に逐次発見する運用を避ける。

全会場分を保存してから `racenote_v054_single_day.py freeze` → `verify` を実行。技術retryでは完了chunkを再予想せず、失敗step/logを一度確認してschema / quality / infrastructureへ分類し、該当箇所だけ修正する。Reader manifestは一度解決し、各raceのcomplete Readerは通常のauthoring passで一度読む。意味のない再取得・tight pollingを避ける。

検証後のみpublicationや結果照合を行う。保存済み予想を障害復旧の都合で再予想・上書きしない。

## 5. Clean-blind / stop conditions

Freeze/Verify前に対象日の結果・払戻・最終オッズ/人気・兄弟lane予想・過去BTDAY印を入力しない。入力の欠損、identity/hash/roster/schemaのfail-closed gateを迂回しない。

正常終了は全対象レースの`FROZEN_CLEAN_BLIND` + Verify PASS。予想を完遂できない場合は失敗したgateと保存済み会場・未保存会場を報告し、架空の予想やFreezeを出力しない。

BTDAY-0077/0078はpre-rebuild監査のみで、r2 performance評価から除外する。

# RaceNote Forecast Baseline Reader v0.2

Status: **CURRENT RESEARCH BASELINE**
Date: 2026-09-29
Logic version: `RaceNote-Baseline-Reader-0.2`

## 1. Purpose

v0.1の基本思想を維持しつつ、1 raceごとの判断を
post-race研究で検証可能にするためDecision Traceを必須化する。

v0.2はBTDAY-0001の結果を見て作ったperformance tuningではない。
BTDAY-0001のpre-result成果物を構造監査した結果、
「印の選択理由が再検証可能な形で残っていない」という実験系の問題を修正する。

## 2. What stays unchanged from v0.1

- Race context first
- Read every runner
- Compare the field
- fixed numeric weightなし
- fixed evidence priorityなし
- Trend top / Ability topの自動◎なし
- Gen0.3 Pairwise / Scenario等を必須化しない
- ◎ = 「今回、自分なら一番買いたい馬」
- ○ = ◎に次いで総合的に買いたい相手
- ▲ = 上位を逆転し得る次候補
- △ = それ以下で馬券候補として残す馬

## 3. Reading method

1. **Race context first**
   - race shape / course / class / distance / field contextを把握する。
2. **Read every runner**
   - 一部候補だけ先に決めない。
3. **Identify the race thesis**
   - 今回の比較で何が重要かを1つ以上言語化する。
4. **Build a candidate cluster**
   - ◎○▲候補を作り、候補外との違いも確認する。
5. **Compare ◎ and ○ directly**
   - 「なぜ◎を○より上に置くか」を具体的に決める。
6. **Record counter-evidence**
   - ◎に不利な最大材料を残す。
7. **Record downweighted evidence**
   - 見たが決定打にしなかった材料を必要に応じて残す。
8. **Record reversal condition**
   - ○/▲が◎を逆転するなら何が起きた時かを書く。
9. **Choose marks**
   - 上記比較の結果として◎○▲△をFreezeする。

## 4. Decision Trace requirement

Canonical contract:

`docs/racenote/FORECAST_DECISION_TRACE_CONTRACT_v0_1.md`

Each usable race must include:

- race_thesis
- decisive_factors: 2–4
- main_vs_second
- strongest_counter
- downweighted_evidence
- reversal_condition

単なる「総合○○・調教○○・厩舎○○」の列挙ではFreeze不可。

## 5. Race-specificity

The prediction must state at least:

- one concrete reason unique to the target race/horse
- one direct comparison between ◎ and ○
- one concrete weakness or uncertainty of ◎

同じ短評テンプレートを使い回してfield値だけ差し替えることは禁止。

同じ文体は許容するが、判断内容はrace-specificでなければならない。

## 6. Missing evidence

予想に必要だがRaceNoteに無い情報を推測で埋めない。

Instead:

- missing_evidenceへ記録
- available evidenceだけで予想
- uncertaintyを上げる
- handoffのracenote_information_gapsへ集約

ただし「不足項目を見つけた」こと自体を、そのturn中のRaceNote仕様変更には使わない。

## 7. Output

Canonical schema:

`schema/racenote_forecast_research_record_v0_2.json`

Human HTML:
- ◎○▲△
- concise axis_comment
- concise concern

Internal canonical record:
- full Decision Trace
- full/top order
- source identity
- Freeze metadata

Human commentは読みやすさ優先。
研究判断はDecision Traceを正本とする。

## 8. Turn discipline

- 1 turn = 2 unused eligible PACI days
- same logic_version for all races
- 1 race = 1 independent forecast
- no result access before every usable prediction Freeze
- no mid-turn logic change

v0.2の結果を見た後に変更する場合はv0.3以降として新version化する。

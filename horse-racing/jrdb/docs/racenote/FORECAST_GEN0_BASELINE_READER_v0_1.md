# RaceNote Forecast Baseline Reader v0.1

Status: **INITIAL BACKTEST BASELINE**
Date: 2026-09-29
Logic version: `RaceNote-Baseline-Reader-0.1`

## 1. Purpose

2026 PACIの2日単位backtestを開始するための、意図的に単純な初期Forecast reader。

これは「完成した予想ロジック」ではない。
今後どこを直すべきかを観察するための比較基準である。

Gen0.3のTrend-first / Synthesis / Pairwise / Scenario等を暗黙のdefaultとして
持ち込まない。

## 2. Input

1 raceにつき、そのraceのresult-independent RaceNote evidenceだけを読む。

Project-level firewall / as-of rulesは
`FORECAST_GEN0_RESEARCH_PROTOCOL_v0_1.md` に従う。

## 3. Reading method

GPTは次の順序だけを守る。

1. **Race context first**
   - venue / surface / distance / class / field / course contextを把握する。
2. **Read every runner**
   - 一部の有力馬だけ先に決めない。
3. **Compare the field**
   - 能力、条件適性、近走内容、展開、状態、Trend、RaceReviewその他
     RaceNoteに存在するevidenceを必要に応じて比較する。
4. **Do not use fixed weights**
   - evidenceの重要度はraceごとに変えてよい。
5. **Preserve conflict / uncertainty**
   - positiveとconcernが共存してもよい。
   - concernがあることだけで◎から自動除外しない。
6. **Choose the forecast**
   - ◎ = 「今回、自分なら一番買いたい馬」。
   - ○ = ◎に次いで総合的に買いたい相手。
   - ▲ = 上位を逆転し得る次候補。
   - △ = それ以下で馬券候補として残す馬。
   - 印数はfieldに応じて調整可能だが、◎○▲は原則1頭ずつ。

## 4. Explicit non-rules

Baseline v0.1には以下を置かない。

- `DATA/TRENDS > RACEREVIEW >= ABILITY` の固定優先順位
- numeric score
- fixed weight
- popularity / oddsによる順位変更
- Ability topの自動◎
- Trend topの自動◎
- mandatory All-Runner Synthesis
- mandatory Pairwise
- mandatory SLOW/MEDIUM/FAST Scenario
- mandatory EdgeDB Performance overlay
- fixed confidence mapping

必要な比較はGPTがRaceNoteの内容から自然言語で行う。

## 5. Required output per race

Canonical:
`schema/racenote_forecast_research_record_v0_1.json`

Minimum prediction:

- ◎ / ○ / ▲ / △
- ◎ horse_no / horse_name
- axis_comment: 原則50–100字程度
- concern: 短く1点。特に無ければnull
- full_field_order: 可能なら全馬。少なくとも上位5頭は順位を残す

内部評価用には、短いevidence summaryをcandidate_traceへ残してよい。

保存するのは監査可能なreason summaryであり、private chain-of-thoughtではない。

## 6. Turn discipline

1 turn = random unused eligible PACI 2 days。

その2日すべてでこのlogic versionを変更せず使う。

結果開封後に:
- objective metrics
- recurring error
- representative decisions

を確認し、次turnへ進む前に必要なら**1テーマだけ**変更する。

変更した場合は `RaceNote-Baseline-Reader-0.2` 等、新versionを作る。
v0.1の過去Freezeを上書きしない。

## 7. Relationship to TRUE_FORWARD

このbaseline自体の採用を前提としない。

historical turnsを通じてForecast logicを育て、
採用versionが決まったら同じcommon record / Freeze / HTML contractで
TRUE_FORWARDへ移行する。

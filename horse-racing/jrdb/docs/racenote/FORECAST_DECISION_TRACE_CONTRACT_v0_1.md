# RaceNote Forecast Decision Trace Contract v0.1

Status: **CURRENT**
Date: 2026-09-29

## 1. Purpose

Forecastの判断を後から検証可能にするため、1 raceごとに
「何を見て」「何と比較し」「なぜ◎を選んだか」を構造化して残す。

このcontractはprivate chain-of-thoughtの保存を要求しない。
必要なのは、結果を見る前に固定できる**監査可能な判断要約**である。

## 2. Required fields

Every usable race must save:

### race_thesis
そのレースで予想上もっとも重要だった論点。
例:
- 前有利か差し有利か
- 距離延長への適応
- 近走着順より内容を優先すべき組み合わせ
- 実績不足で調教/血統比重が上がる新馬戦

単なる「総合的に比較した」は不可。

### decisive_factors
◎を上位に置いた具体的な要因を2〜4件。

Each factor:
- lane: Ability / RecentForm / Suitability / Pace / Training / Trend / RaceReview / Pedigree / Other
- observation: RaceNote上の具体的事実
- interpretation: 今回なぜプラス/マイナスなのか
- source_ref: evidence ID / field / short source locator when available

単なる数値列だけでは不足。
数値を使う場合も「その数値が今回どういう意味を持つか」を書く。

### main_vs_second
◎と○を直接比較する。

Required:
- main horse
- second horse
- why_main_over_second

「総合的に上」は不可。
両馬の具体的な差を1つ以上示す。

### strongest_counter
◎を否定し得る最大の材料。

「展開次第」「上位は接戦」のような全レース共通文だけでは不可。
その馬・そのレース固有の弱点を書く。

### downweighted_evidence
見えていたが決定打にしなかったEvidenceを0〜3件。

Each:
- evidence
- reason_downweighted

例:
- 調教差は小さく決定打にしない
- Trendはsmall-nで方向だけ参照
- 前走着順は不利を受けており額面評価しない

### reversal_condition
○または▲が◎を逆転する条件。
予想順位の不確実性を、レース固有の形で残す。

## 3. Optional fields

- third_candidate_note
- race_specific_note
- missing_evidence
- uncertainty_label
- evidence_conflicts

## 4. Anti-template rule

同じ文章構造を使うこと自体は禁止しない。
しかし、以下はDecision Traceとして不十分:

- 馬名・数値を差し替えただけ
- 「総合的にまとまる」
- 「上位差は小さい」
- 「展開次第」
- 「能力・近走・仕上がりを横並び比較」

だけで判断を説明すること。

各raceのtraceには、そのraceでしか成立しない具体的な比較内容が必要。

## 5. Freeze gate

A usable prediction must not Freeze unless:

- race_thesis non-empty
- decisive_factors count >= 2
- every factor has observation + interpretation
- main_vs_second identifies both horses and a concrete comparison
- strongest_counter non-empty and race-specific
- reversal_condition non-empty
- marks.main matches decision_trace.main_vs_second.main
- marks.second, when present, matches decision_trace.main_vs_second.second
- result_visible_at_freeze = false

A short human-facing axis_comment may be generated from this trace,
but the HTML comment is not a substitute for the canonical trace.

## 6. Research use

Post-result Research thread compares:

- race_thesis vs actual race shape
- decisive_factors vs realized outcome
- main_vs_second comparison vs actual order/content
- strongest_counter whether it materialized
- downweighted evidence whether it should have mattered
- reversal_condition whether it occurred

This enables logic changes to target the actual reading error instead of
guessing from hit/miss alone.

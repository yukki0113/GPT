# RaceNote User-Facing Short Comment v0.2.1

## 1. Status

**OUTPUT/PRESENTATION CONTRACT ONLY — DOES NOT CHANGE v0.2 RANKING**

This contract improves the human-facing explanation attached to the provisionally promoted v0.2 ranking.

It must not alter:

- v0.2 model score;
- ◎○▲△ ranking;
- confidence score;
- betting policies;
- ☆ selection logic.

Purpose: the user ultimately decides whether to spend money. The explanation must therefore make the race-specific judgment auditable and challengeable rather than merely outputting an index ranking.

## 2. Core principle

Every short comment should answer:

> この馬は能力が足りるとして、**今回のコース・枠・脚質・展開・距離で、なぜ買える／なぜ怖いのか。**

Avoid comments that could be copied unchanged to another race.

## 3. Default output

```text
◎ 6 Horse A
○ 5 Horse B
▲ 13 Horse C
△ 15 Horse D
△ 11 Horse E
☆ 15 Horse D    # only when diagnostic value flag exists

展開:
<pace + likely positional shape + important course/draw implication>

◎短評:
<ability>。<today-specific fit>。<clock/distance evidence>。<largest risk>。

○短評:
<why this horse can reverse ◎; include one concrete fit/evidence point>。

▲短評:
<third-rank reason; if value-like, explain the disagreement without forcing a longshot narrative>。

△・☆:
<one concise complementary/value reason>。

買う上での注意:
<single most important uncertainty>

自信度: A/B/C
```

## 4. 展開 comment requirements

State concrete RaceNote-supported facts where available:

- forecast pace;
- number/distribution of 逃げ・先行 vs 差し・追込;
- likely position of important contenders;
- position-rank / forecast-mid-position concern;
- current frame trend if it materially affects the interpretation.

Example:

> ハイ想定。逃げ・先行が7頭おり前は楽ではない。◎は差し型でも予想中団6番手で、後方一気まで下がらない点を評価。

Avoid:

> 差し有利になりそう。

without a concrete field-shape reason.

## 5. Course / frame / style statement

When used as a reason, expose the components rather than writing only `枠・脚質が合う`.

Preferred form:

> 4枠・先行型。4枠の対象レンジ複勝率32%で、予想位置も3-4番手。コース取りの無理が少ない。

If the current model only has separate frame and style evidence and no true interaction statistic, say so implicitly by wording them as separate supporting observations. Do **not** claim a measured `内枠先行有利` interaction unless such cross-statistics actually exist.

## 6. Comparable clock / distance evidence

This is mandatory to discuss for ◎ when relevant to the race.

### 6.1 Direct comparable run

Priority:

1. same venue + same surface + same distance;
2. same/nearby distance under a materially comparable course/condition;
3. nearby-distance evidence as approximation;
4. no legitimate comparison.

When an exact detailed run exists, expose at least:

- run date;
- venue;
- surface/distance;
- track condition if available;
- final time;
- last3F if available;
- 4C / important corner position if available;
- IDM/performance level if useful.

Example:

> 時計は6/1東京芝1800m良1:46.8、上がり34.2、4角5番手。今回と同距離で比較可能な実績があり、能力指数だけでなく実走内容でも距離不安は小さい。

### 6.2 Raw-time comparison caution

Raw time must not be treated as absolute when conditions differ.

If class, going, weight, pace or track-speed context is materially different, state the limitation:

> 1:46.8自体は速いが前走は良馬場。今回の馬場差まで補正した時計ではないため、数値の単純比較はしない。

The current validated v0.2 numerical TimeFit does **not** normalize for these factors. The comment may add contextual caution but must not imply a numerical correction that was not calculated.

### 6.3 Nearby distance

If exact distance evidence is absent:

> 2000mは未経験。1800mの近似実績までは確認できるが、今回は200m延長分を推測で埋めない。JRDB距離適性と脚質を補助材料にする。

### 6.4 No comparable clock

State explicitly:

> **時計比較不可**：同距離・近似距離の詳細履歴が不足。距離適性は不確実性として残す。

Do not convert missing evidence into neutral suitability.

## 7. Ability statement

At least one concrete ability reference should normally be included for ◎:

- IDM;
- total_index;
- recent IDM/performance;
- class-level performance.

But ability should not be the complete reason.

Bad:

> IDM1位で能力上位。本命。

Better:

> IDM62・総合68で能力上位。さらに今回の中団想定と1800m実績が噛み合うため◎。

## 8. Condition/training

Use only when it contributes meaningful evidence.

When cited, state the actual direction/index where available rather than generic `状態良好`.

Do not let training alone overturn a material course/distance deficit.

## 9. ☆ value/disagreement

☆ remains diagnostic until a separate betting test supports it.

If shown, explain:

- pre-target base market rank;
- prediction/ability rank discrepancy;
- race-specific support factor.

Example:

> ☆ 12 Horse D — base市場9位に対し能力圏は4-5番手。今回のハイ想定で差し脚が活きるため、人気だけで切りづらい。

Do not call a horse a value horse only because it is unpopular.

## 10. Risk statement

◎ must have a meaningful risk when one exists.

Priority examples:

- distance extension / clock comparison unavailable;
- frame/style positional cost;
- projected pace pressure;
- forecast position too deep;
- surface/going concern;
- weak recent state;
- small history sample.

Avoid the generic repeated fallback `上位馬との差が小さく、展開ひとつで順位が替わる` when a more concrete failure mode is available.

## 11. Length target

The short comment is for a bettor, not a full research report.

Default target:

- 展開: 1-2 sentences;
- ◎: 2-4 sentences;
- ○: 1-2 sentences;
- ▲: 1-2 sentences;
- △/☆: one sentence each where useful;
- 注意: one sentence.

The goal is **specificity per sentence**, not maximum text volume.

## 12. Audit checklist

Before output, verify:

- [ ] race shape is concrete rather than generic;
- [ ] ◎ has ability evidence;
- [ ] ◎ has at least one today-specific suitability reason;
- [ ] distance/clock evidence is shown or explicitly marked unavailable;
- [ ] raw time is not over-compared across incompatible conditions;
- [ ] a material risk is exposed;
- [ ] frame × style interaction is not claimed unless actually observed/measured;
- [ ] ☆, when present, has both disagreement and race-specific support;
- [ ] no target-result/final-odds leakage.

## 13. Version boundary

This v0.2.1 contract may change wording and evidence presentation only.

If future work changes numerical clock normalization, frame-style interaction, pace coefficients, model weights, candidate selection or mark ranking, that is **not v0.2.1**. It must become a new prediction model candidate (e.g. v0.3) and be validated on untouched races.
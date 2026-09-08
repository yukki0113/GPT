# RaceNote User-Facing Prediction Output v0.3 Candidate

## Status

**CANDIDATE OUTPUT CONTRACT / PREDICTION AND BETTING LOGIC REMAIN SEPARATELY VERSIONED**

This document defines the user-facing per-race presentation format for the current RaceNote prediction work.

The purpose is not to expose every internal factor or raw index. The user should be able to understand, at a glance:

1. what kind of race is expected;
2. how confident the model is in the race-level judgment;
3. why ◎ is buyable;
4. why ○ is one step below ◎ and what could reverse them;
5. why ▲ is the value-oriented second quinella counterpart when a meaningful value candidate exists;
6. which two remaining horses are △1 / △2 in prediction priority order.

Raw JRDB indices may be used internally but should not be copied mechanically into the short comment unless the number itself materially improves interpretability.

## 1. Mark semantics

- `◎`: the horse judged most likely to win under today's conditions.
- `○`: the most reliable alternative to ◎; strongest orthodox opponent.
- `▲`: value-oriented opponent among horses that remain sufficiently competitive on ability and race-specific suitability. It is not merely a longshot slot. If the race is small-field / strongly chalky / has no justified value candidate, ▲ may instead be the ordinary next-ranked contender; when so, state that explicitly.
- `△1`: next prediction-priority contender after the main marks. In many races this may be the pure third-best horse by orthodox strength even when ▲ is used as a value-oriented role.
- `△2`: next prediction-priority contender after △1.

The printed order of the two triangles is meaningful and must be preserved.

Example:

```text
△ 12,3
```

means `△1 = 12`, `△2 = 3`.

Do not sort triangle horse numbers numerically.

## 2. Default per-race output

```text
<venue><race_no>R <race name / class when useful>

レース短評：
自信度：<A/B/C>
<race-shape / upset-risk summary when there is something worth saying>

◎ <horse_no> <horse_name>
<main reason to buy; today-specific suitability; meaningful caution if present>

○ <horse_no> <horse_name>
<main support; why one step below ◎; reversal condition when identifiable>

▲ <horse_no> <horse_name>
<why this horse offers value / disagreement worth buying; if no value role exists, state that this is an orthodox evaluation slot>

△ <△1 horse_no>,<△2 horse_no>
```

Bet selections are not repeated in every short comment when the active betting contract already defines how marks map to tickets.

## 3. Race short comment

`レース短評` reserves two compact pieces of information:

1. first line: `自信度：A/B/C`;
2. second line: one concise race-shape / upset-risk observation when useful.

Confidence is intended as purchase-decision support, not as a synonym for popularity or chalkiness.

- A: major evidence layers broadly agree and unresolved risk is limited;
- B: reasonable top choice but at least one meaningful uncertainty remains;
- C: upper horses are close, evidence is sparse/contradictory, or a major trip/distance uncertainty remains.

A popular favorite can be C. A less-popular horse can be A when the evidence strongly aligns.

Examples:

```text
レース短評：
自信度：A
先行馬が多くハイ寄り。好位差しを優先したい。
```

```text
レース短評：
自信度：C
上位の差が小さく波乱含み。◎も絶対視はしづらい。
```

Keep the second line short. Do not force generic text merely to fill the field.

## 4. ◎ comment

The ◎ comment should answer:

> Why do I want to buy this horse today?

Use the evidence actually relevant to the race. Candidate evidence includes:

- course / frame / running-style fit;
- projected pace and position;
- distance / surface suitability;
- comparable historical performance or time evidence when useful;
- current condition / training;
- ability advantage;
- class / recent-form evidence;
- other race-specific support.

Do not force all factors into one comment.

When there is a meaningful risk, include it naturally.

Preferred style:

```text
能力は上位圏。ハイ想定でも中団前めを取れる差し脚質で展開も向きそう。外枠から想定より位置を下げる形だけ注意。
```

Avoid raw-index transcription such as:

```text
IDM62・総合68だから本命。
```

Raw values may appear in a separate reference view if later desired, but the primary user-facing comment should translate them into an intelligible judgment such as `能力は上位圏`.

## 5. ○ comment

The ○ comment should explain both:

1. why the horse is the strongest orthodox opponent;
2. why it is still below ◎.

When possible, include the reversal condition.

Example:

```text
先行力と距離適性は高く大崩れしにくい。総合的な展開利で◎を上に取ったが、前残りが強まれば逆転まで。
```

Do not merely restate that ○ is second-best.

## 6. ▲ comment

The ▲ comment is especially important because ▲ may carry a different role from the pure orthodox third-ranked horse.

When ▲ is value-oriented, explain:

- why the horse is still competitive enough to buy;
- what race-specific factor supports an upset / overperformance;
- what evidence suggests market or public evaluation may be too low, when available from pre-target-safe information.

Example:

```text
能力差は大きくなく、今回の枠と差し向きの展開なら上位進出余地。近走内容に対して評価が上がりにくいタイプで、妙味込みならここ。
```

Do not choose or praise a horse only because it is unpopular.

If the race does not justify a value-oriented ▲, explicitly switch to the ordinary meaning:

```text
少頭数で妙味候補は作りにくく、▲は純粋な3番手評価。
```

or

```text
堅めの組み立てと見て、▲も妙味枠ではなく上位能力評価。
```

## 7. △ output

No prose comment is required for △1 / △2 by default.

Print only:

```text
△ <△1 horse_no>,<△2 horse_no>
```

The order is prediction priority and must not be reordered by horse number.

Examples:

```text
△ 12,3
```

```text
△ 7,15
```

If a future UI needs horse names, names may be added without changing the priority semantics.

## 8. Brevity rule

The default output should remain readable for an entire race card.

Aim for:

- race comment: confidence + roughly one concise sentence;
- ◎: roughly 1-3 concise sentences;
- ○: roughly 1-2 concise sentences;
- ▲: roughly 1-2 concise sentences;
- △: no prose.

Long explanations belong in an expanded analysis view, not the standard prediction output.

## 9. Evidence discipline

Do not invent a reason simply because a mark was assigned.

If a factor is not actually available or does not materially discriminate the horse, omit it.

Examples:

- comparable time is optional, not mandatory;
- pedigree is optional, not mandatory;
- training is optional, not mandatory;
- race short comment can be minimal if there is no meaningful race-wide insight.

The output should reflect the strongest reasons found by the prediction logic, not a checklist.

## 10. Relationship to betting rules

Marks and comments express the prediction / role judgment.

The active betting contract decides how those marks become tickets. The standard short comment therefore does not repeat the full ticket list unless explicitly requested.

Any future change to quinella / trio / exacta / trifecta construction must be versioned separately from this presentation contract.

# RaceNote Presentation Comment Contract v0.2

Status: FROZEN FOR READER PRESENTATION

## 1. Purpose

This contract defines how RaceNote prediction evidence is rendered into reader-facing Japanese for:

- `horse_short_comment` — each displayed horse comment
- `race_short_comment` — the race-level short summary

It changes presentation only. It must not recompute ranks, marks, confidence, Edge eligibility, or Edge evidence.

The governing principle is:

> Keep implementation vocabulary in audit/detail data, and translate it into ordinary racing language before it reaches the newspaper reader.

## 2. Reader-facing terminology

| Internal concept | Reader-facing wording | Notes |
| --- | --- | --- |
| `good` / base Good | 基礎総合評価 | Not a probability or expected return. Do not expose the raw field name by default. |
| `axis_eligible` / `axis_good_guard` | 逆転許容圏内 / 逆転許容圏外 | Exact threshold and score gap belong in audit/detail views unless explicitly requested. |
| positive performance Edge polarity | プラス | Means historical performance tendency supports the horse. |
| neutral performance Edge polarity | 中立 | No directional performance advantage from the Edge comparison. |
| negative performance Edge polarity | マイナス | Means historical performance tendency is adverse. |
| `axis_changed=true` | ◎へ変更 | Explain the comparison that caused the change. |
| `axis_changed=false` | ◎据え置き | Edge detail may be omitted if it did not materially affect the mark. |

Do not expose implementation labels such as `Good`, `base_good`, `ability_good`, `suitability_good`, `forecast_good`, `performance_edge_tier`, `performance_edge_polarity`, `family_vote_sum`, `axis_good_guard`, `axis_eligible`, `mark_decision_role`, `POSITIVE`, `NEUTRAL`, or `NEGATIVE` in ordinary reader-facing comments.

## 3. Each-horse comment logic

Each-horse comments explain why that horse deserves its displayed mark. They should prioritize horse-specific evidence rather than repeating race-wide mechanics.

Use the following order of thought:

1. Explain the horse's main base strengths or risks in ordinary Japanese.
2. If Edge materially explains the displayed mark, add the Edge direction as `プラス`, `中立`, or `マイナス`.
3. If the horse became the axis because of Edge, it is acceptable to say `Edge比較で◎へ変更`.
4. If the horse was the original base-evaluation leader but lost the axis, it is acceptable to say that it was `基礎総合評価1位` but the Edge comparison worked against it.
5. Do not repeat the full two-horse reversal mechanics in every horse comment. The race summary owns that explanation.

The comment should describe evidence, not recreate the prediction model.

## 4. Race short-summary logic

The race summary explains the race-wide selection logic. Pace and selection method remain important, but an axis reversal caused by Edge must be explained in reader-facing language.

When the axis changes, the preferred structure is:

1. State the horse that led the base evaluation.
2. State that the selected challenger was close enough to be in the reversal window.
3. Compare the relevant Edge directions.
4. State that the axis was changed.

Example:

> 基礎総合評価では12ロンドボスが1位。4ダガーリングは逆転許容圏内の僅差2位。Edge比較ではロンドボスがマイナス、ダガーリングが中立のため◎をダガーリングへ変更。

When the axis does not change, a concise form is sufficient:

> 基礎総合評価で12ロンドボスが首位。Edge比較でも判断を覆す材料はなく、◎は据え置き。

If Edge did not materially affect the marks, the race summary does not need to mention Edge merely because matches exist.

## 5. Double-counting guard

`good` is already a composite base evaluation. Components such as ability, suitability, training/condition, and JRDB finish forecast contribute to that base evaluation.

Therefore, once the summary says `基礎総合評価`, a component must not be presented as a second independent post-Edge vote.

Bad framing:

> 基礎総合評価で僅差。Edgeで逆転。さらにJRDBゴール予測3位も後押し。

If the JRDB finish forecast was already included in the base score, this wording makes one input look like an additional independent reason.

Acceptable framing:

> 基礎総合評価では僅差。その評価にはJRDBのゴール予測も含まれる。最終的にEdge比較で◎を変更。

In ordinary short comments, even this explanatory detail can usually be omitted unless it materially improves readability.

## 6. Edge interpretation guard

Performance Edge and betting-value Edge are separate concepts.

A reader-facing `プラス` / `中立` / `マイナス` in the axis-selection explanation refers to performance direction unless explicitly stated otherwise. Do not imply that a performance-positive Edge automatically means value, expected return, or a profitable bet.

## 7. Detail and audit views

Raw implementation fields, exact score gaps, guard thresholds, vote sums, family votes, and Edge IDs may remain available in audit/debug/detail data for traceability.

They are not forbidden as data. They are forbidden as unexplained ordinary reader-facing prose.

## 8. Presentation-layer boundary

This contract belongs to the presentation layer only.

The presentation layer must not:

- recompute or reorder marks;
- change the frozen axis decision;
- invent Edge evidence;
- reinterpret Edge performance direction as betting value;
- re-run Edge matching;
- expose raw internal identifiers as the normal explanation.

Prediction and Edge policy remain authoritative upstream. Presentation only explains the already-frozen result in readable Japanese.

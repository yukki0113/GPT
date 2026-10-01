# RaceNote Reader-Facing Forecast Prose Contract v0.1

Status: **ACTIVE CANDIDATE — READER-FACING ONLY**
Date: 2026-10-01
Applies to: RaceNote-Human-Context-Reader-0.4.1-candidate and later unless superseded
Scope: reader-facing forecast prose only

## 1. Purpose

This contract governs how a Frozen forecast is written for the reader.

It does **not** decide the marks.

Forecast selection logic and reader-facing prose are separate layers:

~~~text
race reasoning
  -> marks are decided
  -> audit trace is preserved
  -> reader-facing forecast is written naturally from the actual evidence
~~~

The prose layer must not change ◎ / ○ / ▲ / △1 / △2 after Freeze.

The target style is the earlier RaceNote forecast style typified by BTDAY-0003: concrete race evidence is interpreted in ordinary racing language, then connected to today's expectation.

The target publication surface is the newspaper PWA race-short-comment section. Therefore the default output is **one compact paragraph per race** rather than separate paragraphs for each mark.

## 2. Core writing principle

Write **why these horses are worth buying in this race**.

Do not write **why each horse satisfies the definition of its mark**.

The normal flow is:

~~~text
◎ main evidence and interpretation
  -> ○ concise opponent case
  -> ▲ concrete single-shot reason
~~~

This is not a mandatory sentence template. The order may bend when the race reads more naturally another way, but the whole race should remain readable as one compact paragraph.

The paragraph should feel like one race comment, not three mini-comments pasted together.

## 3. Race-specific evidence first

Use only evidence that materially affected the judgment. Useful material may include what happened in a prior race beyond the finish position, course / distance / surface change, class / opponent context, pace or position, how the horse moved through the race, late strength or inability to sustain it, current training / condition, direct-condition history, RRDB reinterpretation translated into ordinary racing language, and a concrete reason today's setup may be better or worse.

Raw values may appear when they genuinely clarify the point, but the prose must not become a field dump.

Prefer:

> 前走は8着でも道中で位置を上げており、今回は1700mへ戻るのがプラス。

over:

> IDM 36.1、近3走3・9・9着、同距離1回馬券圏、調教平行線。

The second form may remain in the audit trace. It is not the target reader-facing style.

## 4. Interpret before concluding

A finish position alone is not an explanation.

When useful, say what was hidden inside the visible result: moved early and paid for it late, made ground despite an unfavorable pace, was unable to secure position, showed class-compatible speed, had a better run than the placing suggests, or had a favorable trip that may not repeat.

Translate RRDB findings into this kind of ordinary race interpretation.

Do not print internal labels such as UPGRADE / DOWNGRADE / CONFIRM / hidden_strength / Next-Watch grade merely as reader-facing justification. If such evidence mattered, translate it into ordinary racing language.

## 5. One-paragraph race comment

The standard reader-facing output for a race is one paragraph.

Within that paragraph:

- ◎ receives the most space because it is the main forecast judgment;
- ○ is usually explained more briefly, with the strongest concrete reason it belongs in the main line;
- ▲ receives enough space to make the specific upset / reversal reason understandable;
- △1 / △2 do not need to be forced into the short comment unless there is a particularly useful race-wide point to mention.

Do not force equal sentence counts or equal word counts for ◎ / ○ / ▲.

Do not create a rigid pattern such as:

> ◎ explanation. ○ is the main opponent. ▲ has upset potential.

The paragraph should read as continuous racing analysis.

## 6. Mark words are optional, mark definitions are not prose

It is acceptable to write 「本命にします」「対抗にします」「単穴で狙います」「押さえます」 when they fit naturally.

It is not acceptable to fill the explanation with the internal definition of the mark.

Avoid reusable role statements such as 「勝ち切る現実性まで含めて最も買いたい」「◎以外では最も相手評価を上げたい」「安定度では本線に譲る」「展開ひとつで◎○を逆転できる単穴」「5頭候補に残す」. Those are decision metadata, not racing analysis.

Likewise, phrases such as 「相手本線」「対抗視」 are allowed, but they must not become mandatory connectors used in the same place every race.

## 7. ◎ prose

For ◎, explain the strongest concrete reason the horse deserves to be the main bet today.

The prose does not need to prove a formal winning path.

Good ◎ prose may show a prior run whose content is stronger than the result, a return to a suitable condition, current improvement that connects directly to today's setup, a race-shape advantage, evidence the horse can sustain a race-winning move, or opponent / class context that makes today's task more realistic.

Do not end every ◎ portion with the same declaration.

The conclusion may be direct and ordinary: 「巻き返しを期待します。」「ここでは最も買いやすい馬です。」「本命にします。」「押し切りまで見ます。」 Or omit an explicit conclusion when the preceding analysis already makes the judgment clear.

## 8. ○ prose

○ should be written as a horse, not as 'the second slot'.

In the one-paragraph format, ○ is usually concise. State the strongest race-specific reason it remains the principal opponent.

Do not mechanically contrast ○ with ◎. Do not force a reliability / stability story. If the meaningful point is the same kind of strength as ◎, say so.

A short natural clause is enough when the case is straightforward.

## 9. ▲ prose

▲ must expose the actual asymmetric reason that justified the independent single-shot selection.

The prose should answer **何が起きれば、この馬が本線を崩せるのか** through concrete racing material, not through a canned upset-path sentence.

Explain the condition change, hidden prior-run strength, pace interaction, position change, preparation change, or other specific source of upside.

Do not write 「一発の材料」 unless the material itself is named immediately and specifically. Do not call a horse a longshot or outsider from inferred popularity.

Because the race comment is one paragraph, ▲ should normally appear after the main-line discussion as the final concrete twist in the race view. This is a presentation preference, not a selection rule.

## 10. △ prose

△ comments are not required in the newspaper short comment.

If a △ horse is mentioned, state the concrete reason briefly. Do not manufacture a dramatic story for every supporting horse.

The full marks remain available elsewhere in the newspaper PWA.

## 11. Variation comes from the race, not from synonym rotation

Do not solve repetition by rotating synonyms through a template. Sentence structure should vary because the evidence varies.

A comment may start from the last race, a condition change, current training, pace / field composition, class context, a hidden-strength interpretation, or direct course evidence. There is no mandatory opening or closing phrase.

One paragraph does not mean one sentence skeleton.

## 12. Anti-template check

Before Freeze, compare reader-facing comments across the card.

If many races share the same sentence skeleton with only horse names and fields swapped, rewrite the prose.

A useful test is: **Could this paragraph be pasted onto several other races by changing only horse names and one or two facts?** If yes, it is too generic.

Also check whether ○ is always introduced by the same connector or ▲ is always closed with the same "upset" phrase. If so, rewrite from the race evidence.

## 13. Audit separation

Audit fields may remain structured and repetitive. mainline_cases, single_shot_case, rrdb_evidence, and mark_reason may use concise controlled language for verification.

Do not copy those fields directly into reader_facing_reason.

The reader-facing paragraph should be regenerated from the underlying evidence and the Frozen decision.

## 14. Style anchor examples

Preferred single-horse style anchor:

> ベルアズーロを本命にします。前走は8着でも道中で位置を上げており、今回は1700mへ戻るのがプラスです。先行できる形もあり、巻き返しを期待します。

Preferred one-paragraph race-short-comment shape:

> ペルウィクトールは前走で内が開かず外へ切り替えながら3着まで来ており、今回は調教も高水準。スムーズならもう一段前進できる。ハヤブサブローも前で運べる形なら崩れにくいが、タッカーヴァンバンは後方から押し上げて止まらなかった前走内容が目立ち、流れが向けば頭まで届く余地がある。

The purpose of these examples is their structure:

~~~text
main judgment
  -> concise main-line opponent
  -> concrete asymmetric alternative
~~~

Do not copy their wording as a new template.

## 15. Summary

Reader-facing RaceNote prose should feel like a person who watched and understood the race, compressed into one newspaper-ready paragraph.

~~~text
marks come from the forecast logic
comments come from the race evidence
one race = one compact paragraph
◎ is the center
○ is concise
▲ is concrete
internal roles stay internal
~~~

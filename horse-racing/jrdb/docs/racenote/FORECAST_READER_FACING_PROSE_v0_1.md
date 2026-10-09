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

Write one short piece of racing analysis, not a serialization of the five
marks.

The marks are already shown elsewhere. The comment should preserve the actual
shape of the race judgment in ordinary racing language: what gives ◎ its
winning case, what keeps ○ dangerous, where the important tension lies, and
what specific route allows ▲ to overturn the main line when that matters.

The prose should be faithful to the relative strength of the judgment. If ◎
was clearly preferred to ○ for a concrete race-specific reason, the comment may
read clearly. If the two were close and the order turned on one narrower
tie-break, the comment should preserve that closeness rather than upgrading the
choice into a strong declaration. If ◎ needs a particular setup, the setup
belongs in the explanation.

This is not a separate confidence-writing task. Do not choose stronger or
weaker language in order to create a useful research label. Later analysis may
read the frozen comment as evidence about how decisive the forecast was, but
the writing stage only records the judgment that already exists.

There is no preferred sentence order such as ◎ -> ○ -> ▲ -> △1 -> △2.
Mention only the horses needed to make the race view understandable.

A good test is whether the paragraph would still read naturally if the mark
symbols were removed, and whether its degree of certainty would still match
the underlying race analysis if no later research existed.

## 3. Translate evidence into racing language

Reader-facing prose should normally describe what happened or what changes
today:

- where the horse was positioned and how it moved;
- whether the previous placing understated or overstated the run;
- course, distance, surface, pace or class change;
- training/condition change when it connects to today's race;
- a concrete reason the race shape can improve or worsen.

Internal evidence sources and numeric aids belong primarily in the Decision
Core. RRDB, IDM, internal index names, decision roles and signal labels should
normally be translated into ordinary racing language.

For example, prefer:

> 前走は最後方からでも直線で脚を使えており、流れが速くなれば差し込みまである。

over:

> RRDBでも高評価でIDM62。

A raw number may appear only when that number itself is unusually informative
to the reader. It should not be the sole reason for a mark.

## 4. One paragraph, variable shape

The standard newspaper comment is one compact paragraph, but one paragraph
does not imply one sentence skeleton.

It may begin with:

- the main horse;
- a race-shape observation;
- a condition change;
- a notable previous run;
- a tightly matched group when no single horse dominates.

◎ usually receives the most explanation. ○ and ▲ receive only the space their
actual evidence needs. △1 / △2 need not be mentioned unless they add useful
race context.

Avoid habitual endings that merely enumerate the remaining marks, such as
「XとYまで」, when they add no information.

## 5. ▲ prose

▲ must reveal the concrete asymmetric reason for the independent single-shot
selection.

The reader should be able to understand what change in pace, position,
condition, preparation or hidden prior-run strength gives that horse a path to
beat the main line.

Calling it 「一発候補」 or 「逆転候補」 is not an explanation by itself.
Those words are fine only after the actual source of upside is clear.

## 6. Card-level prose review

Before Freeze, read the comments as a card rather than validating each race in
isolation.

Look for repeated structure, especially:

- every race starting with ◎ and then mechanically moving to ○ and ▲;
- repeated 「一発候補」「逆転候補」 without race-specific explanation;
- repeated 「XとYまで」 endings;
- direct exposure of internal terms such as RRDB / decision-role labels where
  ordinary racing language would say the same thing better.

This review changes prose only. It never changes the Frozen mark decision.


## 7. ◎ and ○ prose

The main-line discussion should make the actual ◎/○ relationship
understandable without turning the paragraph into a comparison worksheet.

For ◎, explain the strongest concrete reason the horse deserves to be the main
bet today. This may be a prior run whose content is stronger than the result, a
return to suitable conditions, current improvement, a race-shape advantage, an
ability edge, or another observation that creates a realistic winning route.

For ○, state the strongest reason it remains the principal opponent. Write ○ as
a horse, not as "the second slot".

Where the race analysis genuinely separates them, let the decisive point be
visible. For example, ◎ may control the position while ○ needs the race to come
back, or ◎ may have shown the stronger class evidence while ○ is preferred
mainly for repeatability. Where they are close, a short natural description of
both cases plus the real tie-break is better than an exaggerated contrast.

The prose does not need a ceremonial declaration such as "◎ is clearly
superior" or "○ is only second best". Concrete racing evidence should carry
the comparison. Likewise, do not mechanically manufacture a reliability story
for ○ simply because it wears the second mark.

An explicit conclusion such as 「本命にします」「押し切りまで見ます」 is
optional. Omit it when the preceding analysis already makes the judgment clear.

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

Audit fields may remain structured and comparatively controlled because they
serve verification. The reader-facing paragraph should be regenerated from the
underlying evidence and the Frozen decision rather than copied from those
fields.

The audit layer and reader-facing layer must nevertheless describe the same
judgment strength. A close ◎/○ call must not become emphatically one-sided only
in the newspaper comment, and a genuinely decisive comparison must not be
flattened into generic equal-treatment prose.

Neither layer should encode a downstream research category directly. The
research process reads the frozen forecast record after authoring; it does not
supply wording targets to the authoring process.

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

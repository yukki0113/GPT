# RaceReviewDB Next-Watch Operation v0.1

Status: OPERATIONAL  
Date: 2026-09-25

## 1. Purpose

Provide a simple daily operational interface for asking:

- "9/22の次走注目馬をお願いします"
- "2026-09-22の次走注目馬をお願いします"

The system returns S and A next-start attention horses from races completed on
the requested source date.

The objective is not standalone betting profitability. The intended use is an
additional evidence layer for RaceNote, RL index, and other horse-evaluation
systems.

## 2. Canonical inputs

RaceReviewDB CURRENT:

- Drive file ID:
  1UwNfrupMTHRPhkzULPvClGre4MWz2TFg
- stable file:
  RaceReviewDB_CURRENT.zip

Frozen Discovery rule contract:

- Drive file ID:
  1AzhPgqr8GXei4opzbI8gD7nb4-5qZ3Zr
- rule version:
  next-watch-rules-discovery-v0.1

The operational selector must use the frozen rule thresholds. It must not
re-optimize thresholds for the requested date.

## 3. Source-date contract

For requested date D:

1. load RaceReviewDB CURRENT
2. select completed flat JRA horse starts with race_date = D
3. derive within-horse history features using only starts strictly before D
4. apply frozen hidden-value rules
5. assign S / A
6. return no candidate when no horse qualifies

No next-start result is read by the selector.

## 4. Standard S/A contract

Only hidden-value rules HV* are used for standard S/A.

Persistence-only P01/P03 are excluded from the standard list because those
horses are already obvious from source finishing position and are more likely
to be represented by RaceNote / RL without a dedicated Next-Watch boost.

S:

- match HV05 or HV13, OR
- match at least two frozen hidden-value rules

A:

- match at least one frozen hidden-value rule
- and not satisfy S

There is no forced minimum number of S or A horses.

Valid outputs include:

- S 0 / A 0
- S 0 / A several
- S several / A 0
- S several / A several

Quality takes priority over list length.

## 5. Frozen hidden-value rules

The operational selector reads the exact frozen rule contract rather than
duplicating thresholds in chat.

Current hidden-value rule IDs:

- HV01
- HV02
- HV03
- HV05
- HV06
- HV07
- HV11
- HV12
- HV13

These were discovered in 2026-05 through 2026-07 and validated without
threshold re-optimization on historical 2024-2025 OOS data.

## 6. User-facing response

Default response should be compact.

For each horse show:

- grade S / A
- horse name
- source race and horse number when useful
- source finish
- concise reasons derived from matched frozen rules

Example format:

S
- Horse A — 4th
  performance strong + strong last3F + self-history improvement

A
- Horse B — 6th
  elite last3F

If no horse qualifies:

- S: none
- A: none

Do not pad the list.

## 7. Execution assets

Selector:

- horse-racing/jrdb/src/jrdb_next_watch_select.py

Workflow:

- .github/workflows/jrdb-next-watch-select.yml

Issue-trigger route is also available through the registered Next-Watch
workflow using a title such as:

[JRDB_NEXT_WATCH_SELECT] 2026-09-22

## 8. Smoke test

Source date:

2026-09-22

Run:

36115281667

Result:

- source starts: 147
- S: 4
- A: 10
- status: PASS

S horses in the smoke test:

- ロイスター
- コスモバルムンク
- グレイテストソング
- ハッスルダンク

Artifact:

- RaceReviewDB_NextWatch_Select_2026-09-22_g36115281667.zip
- Drive file ID:
  16bm8KNyDewqaakzpwkbrNUZUPuDUqf5B

## 9. Operational request interpretation

When the user asks:

"xx/xxの次走注目馬をお願いします"

interpret xx/xx as the completed source-race date for the applicable year in
context, resolve it to YYYY-MM-DD, run the selector, and return S/A.

If the requested date is outside RaceReviewDB CURRENT coverage, report that
fact rather than guessing.

## 10. Integration intent

Next-Watch is an additive signal.

Recommended downstream use:

RaceNote / RL base evaluation
+
Next-Watch S/A evidence

Next-Watch should not independently override all other evidence solely because
a horse is S or A.

Future integration can expose:

- next_watch_grade
- matched_rule_count
- matched_rule_ids

as downstream features for RaceNote / RL.


## 11. Reverse lookup from future PACI

The operational system also supports the inverse workflow:

future PACI entrants
->
stable horse_id from KYI blood registration number
->
most recent completed flat JRA start before the target date
->
reconstruct the frozen Next-Watch source features at that previous start
->
apply the same hidden-value S/A rules

This allows requests such as:

- "取得したPACIを基にS/A相当の出走馬がいるか確認して"
- "明日の出走馬の中に次走注目馬がいるか見て"

Implementation:

- horse-racing/jrdb/src/jrdb_next_watch_reverse.py

PACI identity:

- KYI blood registration number is used as horse_id
- horse-name joins are prohibited
- horses with no usable previous RaceReviewDB start remain unclassified

Reverse grading is identical to normal operational grading:

- S:
  HV06 or HV13 match, OR HV05 plus at least one independent additional signal
  from HV07 / HV11 / HV12
- A:
  at least one frozen hidden-value rule match and not S
- no forced minimum count

### Reverse smoke test

PACI:

- PACI260926.zip
- Drive ID:
  1PSYw6uL2Gx-rbtcJsgsGFZZNGTnMc4od

Target race date:

- 2026-09-26

Workflow run:

- 36130085663

Entrants:

- 313

Result:

- S:
  18
- A:
  22
- no usable prior history:
  60

Artifact:

- RaceReviewDB_NextWatch_Reverse_2026-09-26_g36130085663.zip
- Drive file ID:
  1-uMaG1uK8WQ-6v9oVqGcbnBwbGJVGCyg

The reverse workflow reads only completed prior starts from RaceReviewDB. It
does not use any target-race result.


## 12. S-grade tightening 2026-09-26

The original operational S rule produced too many candidates in live use
(28 S horses for 2026-09-27).

The S contract is therefore tightened for operational readability while keeping
the same frozen underlying HV rules.

New S:

- HV06 match:
  6th-or-worse source finish + strong performance + strong last-3F
- OR HV13 match:
  elite performance + elite last-3F
- OR HV05 plus at least one independent extra signal:
  HV07 (position recovery) or HV11/HV12 (own-history improvement)

A:

- at least one frozen hidden-value rule match
- and does not satisfy the stricter S rule

Derived hierarchical duplicates such as HV01+HV02 alone or HV03+HV07 alone do
not promote a horse to S.

Smoke application to 2026-09-27:

- old S count: 28
- tightened S count: 5

Tightened S horses:

- スワローシチー
- サンライズバブル
- セブンサークル
- ロクメイカン
- テンタイムトップ

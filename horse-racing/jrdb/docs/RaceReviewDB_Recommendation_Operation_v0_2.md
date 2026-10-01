# RaceReviewDB Recommendation Operation v0.2

Status: OPERATIONAL

> SUPERSEDED for current operation by the v0.3 four-signal contract. Retained for historical reference.
Date: 2026-10-01

## 1. Purpose

RaceReviewDB (RRDB) exposes post-race recommendation signals that reinterpret a
horse's prior run for the next start.

This is not a standalone betting strategy and not a score.

Normal requests such as:

- "9/27の次走推奨馬をお願いします"
- "明日の出走馬の中にRRDB推奨馬がいるか確認して"

return horses matching one or more current recommendation signals.

## 2. Current recommendation contract

Current contract version:

`rrdb-recommendation-signals-v0.2`

Canonical implementation:

`horse-racing/jrdb/src/jrdb_recommendation_signals.py`

Current operational signals:

1. `TIME_CLASS_PLUS1`
   - 上位クラス時計
   - Historical time-class equivalent is at least one class above the declared class.
2. `FRONT_SURVIVE_GAP05`
   - 前傾前受け耐性
   - pace percentile >=70, corner4 frontness >=0.60, winner gap <=0.50 sec.
3. `REAR_HIGH_LAST3F90`
   - 後傾差し逆行
   - pace percentile <=30, corner4 frontness <=0.40, last3F speed percentile >=90.
4. `HV01`
   - 4着以下＋補正タイム上位20%。
5. `HV02`
   - 6着以下＋補正タイム上位20%。

The HV01/HV02 performance Q80 threshold remains frozen from the prior accepted
research contract. They are retained because they reproduced in 2024-2025 OOS.

## 3. Grade policy

S/A recommendation grades are disabled.

Current outputs must not rank a horse higher merely because:

- multiple signals coexist;
- hierarchical signals overlap;
- matched signal count is larger.

Expose:

- matched signal IDs;
- human-readable signal labels;
- measured strength values.

Multiple signals may be shown together, but signal count itself is not a grade.

## 4. Strength display

Do not convert the latest strength study into new S/A cutoffs.

Preferred display:

- TIME_CLASS: class gap / time-class equivalent;
- FRONT: winner gap, pace percentile, corner4 frontness;
- REAR: last3F percentile, winner gap, pace percentile, corner4 frontness;
- HV01/HV02: performance signal, fixed performance band, source finish.

Current research found useful gradients but not enough strictly monotone evidence
to freeze a universal strength grade.

## 5. Historical retention

Operational CURRENT consumer lookback:

`730 days`

Reason:

RRDB recommendation is primarily a prior-run reinterpretation lane. Normal
forecast consumption does not require the entire research history in the
operational CURRENT.

Policy:

- current/recommendation consumers must ignore history older than 730 days from
  the target date;
- publication may compact future `RaceReviewDB_CURRENT.zip` generations to a
  rolling ~2-year operational window;
- research/OOS/history rebuild sources remain separate and may retain longer
  history;
- do not delete historical Warehouse / immutable research artifacts merely
  because CURRENT is compacted.

A 2-year window is preferred over 1 year so lightly raced horses and long layoffs
remain reasonably covered.

## 6. Source-date operation

For completed source date D:

1. load validated RaceReviewDB CURRENT;
2. read source-date flat JRA horse starts;
3. join race pace context;
4. apply the v0.2 recommendation contract;
5. return all matching horses;
6. show signal evidence and measured strength;
7. do not assign S/A.

No future next-start result is read.

## 7. Future-PACI reverse lookup

For target date D:

1. read PACI horse identities;
2. join by JRDB blood registration number;
3. find the latest completed flat JRA start with:
   - `race_date < D`
   - `race_date >= D - 730 days`;
4. apply the same v0.2 recommendation contract;
5. return MATCH / NO_MATCH / NO_PRIOR_HISTORY;
6. no horse-name fallback;
7. no S/A grade.

## 8. RaceNote / Forecast use

RRDB remains one evidence lane.

Forecast should read the measured recommendation signals and ask:

> Does this prior-run evidence change how the visible recent result should be
> interpreted in today's race?

RRDB must not become:

- automatic ◎ / ○ / ▲;
- a fixed numeric bonus;
- a standalone betting recommendation;
- a signal-count score.

The current prediction model may materially use a strong RRDB signal when
relevant to today's class/course/distance/pace context.

## 9. Legacy boundary

The old Next-Watch S/A contract and frozen HV combinations remain for historical
reproduction only.

Legacy assets include:

- `jrdb_next_watch_rules.py`
- `RaceReviewDB_NextWatch_Operation_v0_1.md`
- frozen `next-watch-rules-discovery-v0.1` artifact

They are not the current operational recommendation contract after 2026-10-01.

## 10. Evidence basis

The v0.2 cutover is based on:

- 2024-2025 Historical OOS ability validation;
- 2024-2025 SED market enrichment;
- signal strength / monotonicity study.

Key interpretation:

- TIME_CLASS_PLUS1 reproduced as an ability signal;
- FRONT_SURVIVE_GAP05 showed strong next-start ability lift;
- REAR_HIGH_LAST3F90 reproduced as a pace-opposition signal;
- HV01/HV02 retained predictive value and relative market value;
- strength gradients are displayed as measured values rather than promoted to
  formal grades.

## 11. Canonical ownership

Code / contract / docs:

GitHub `main`.

Operational RRDB data:

stable Drive `RaceReviewDB_CURRENT.zip`.

Research artifacts and long-history evidence are not the operational CURRENT
contract.

## 12. Response format

Default example:

```text
○○
- 上位クラス時計: class gap +1.3
- 前傾前受け耐性: 勝ち馬0.22秒差 / pace pct 84 / 4角frontness 0.78

△△
- 後傾差し逆行: 上がり98pct / 勝ち馬0.31秒差
```

Do not prepend S/A.

Do not sort solely by matched signal count.

If ordering is needed, prefer race order / horse number unless a downstream
forecast layer supplies its own ranking.


## 13. Newspaper/PWA presentation boundary

RaceNote internal consumers may read full signal IDs and measured strength.

Newspaper/PWA uses a separate reader-facing handoff:

`docs/RaceReviewDB_Newspaper_Handoff_v0_1.md`

The handoff is sparse and contains only matched target-horse identity plus one
RRDB-generated short comment and contract version. Newspaper/PWA must not expose
internal signal IDs, signal counts, raw strength JSON, or S/A grades.

Reader-facing canonical phrases are intentionally concise:
- 前走時計はクラス水準より上。
- 前傾ラップ戦を前で受け、勝ち馬と僅差まで踏ん張った。
- 後傾ラップ戦も後方から上位の上がりは使った。
- 敗戦でもタイムは水準以上。

PWA presentation reuses the existing RaceNote mark cell. Keep an existing
RaceNote mark; if none exists, show 注. In either case the mark opens the modal
containing the RRDB short comment.


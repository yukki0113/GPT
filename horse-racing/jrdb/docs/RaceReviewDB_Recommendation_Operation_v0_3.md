# RaceReviewDB Recommendation Operation v0.3

Status: OPERATIONAL
Date: 2026-10-01
Supersedes: `RaceReviewDB_Recommendation_Operation_v0_2.md`

## 1. Purpose

RaceReviewDB (RRDB) exposes post-race recommendation signals that reinterpret a
horse's latest prior run for the next start.

The operational Newspaper/PWA target is a compact set of horses whose prior-run
evidence is worth surfacing as a reader-facing `注` candidate. RRDB remains one
evidence lane; it is not a standalone betting system and does not assign S/A grades.

Normal requests such as:

- "9/27の次走推奨馬をお願いします"
- "明日の出走馬の中にRRDB推奨馬がいるか確認して"

return horses matching one or more of the four current recommendation signals.

## 2. Current recommendation contract

Current contract version:

`rrdb-recommendation-signals-v0.3`

Canonical implementation:

`horse-racing/jrdb/src/jrdb_recommendation_signals.py`

Current operational signals are exactly:

1. `TIME_CLASS_PLUS1`
   - 上位クラス時計
   - Historical time-class equivalent is at least one class above the source run's declared class.

2. `FRONT_SURVIVE_GAP05`
   - 前傾前受け耐性
   - pace percentile >= 70
   - corner4 frontness >= 0.60
   - winner gap <= 0.50 sec

3. `REAR_HIGH_LAST3F90`
   - 後傾差し逆行
   - pace percentile <= 30
   - corner4 frontness <= 0.40
   - last3F speed percentile >= 90

4. `HV02_Q85_Q90`
   - 6着以下＋補正タイムQ85以上Q90未満
   - source finish >= 6
   - performance_signal >= Q85
   - performance_signal < Q90

Fixed operational thresholds:

- Q85 = `0.03422932330827132`
- Q90 = `0.16777149321267684`

Q85 was fixed for this operational cutover from the 2026-08〜09 fine-band
study and then checked without recomputation on 2026-06〜07. In the four-month
2026-06〜09 exploratory comparison, HV02 Q85–Q90 had N=154, next-start top3
rate 29.22%, and place ROI 125.39%. The same band's top3 rate was 29.87% in
2026-06〜07 and 28.57% in 2026-08〜09.

This is serving evidence for the v0.3 cutover, not a claim that Q85 is a
universal or permanently optimized percentile threshold.

## 3. Disabled broad HV signals

The following are no longer operational recommendation signals:

- `HV01`: 4着以下＋補正タイム上位20%
- broad `HV02`: 6着以下＋補正タイム上位20%

They may remain in historical research artifacts for reproduction and analysis,
but current recommendation output must not return them.

The narrowed `HV02_Q85_Q90` replaces broad HV output for current operation.

## 4. Grade policy

S/A recommendation grades are disabled.

Current outputs must not rank a horse higher merely because:

- multiple signals coexist;
- matched signal count is larger;
- one signal has a larger raw measured value.

Expose internal signal IDs and measured strength to RaceNote, but do not convert
signal count into a score or grade.

## 5. Strength display

Preferred internal strength fields:

- TIME_CLASS: class gap / time-class equivalent
- FRONT: winner gap, pace percentile, corner4 frontness
- REAR: last3F percentile, winner gap, pace percentile, corner4 frontness
- HV02_Q85_Q90: performance_signal, performance band, source finish

For HV02_Q85_Q90 the band itself is the operational selector; Q95+ is not a
stronger recommendation tier and is not returned merely for being more extreme.

## 6. Historical retention

Operational CURRENT consumer lookback:

`730 days`

For target date D:

- source run must satisfy `race_date < D`
- source run must satisfy `race_date >= D - 730 days`
- horse identity is JRDB blood registration number
- horse-name fallback is prohibited

This is a serving boundary. Do not physically truncate RaceReviewDB CURRENT
until baseline-history-state decoupling permits safe compaction.

## 7. Source-date operation

For completed source date D:

1. load validated RaceReviewDB CURRENT;
2. read source-date flat JRA horse starts;
3. join race pace context;
4. apply the v0.3 four-signal contract;
5. return all matching horses;
6. show signal evidence and measured strength internally;
7. do not assign S/A.

No future next-start result is read.

## 8. Future-PACI reverse lookup

For target date D:

1. read PACI horse identities;
2. join by JRDB blood registration number;
3. find the latest completed flat JRA start within the 730-day lookback;
4. apply the same v0.3 four-signal contract;
5. return MATCH / NO_MATCH / NO_PRIOR_HISTORY;
6. no horse-name fallback;
7. no S/A grade.

## 9. RaceNote / Forecast use

RRDB remains one evidence lane.

Forecast asks:

> Does this prior-run evidence change how the visible recent result should be
> interpreted in today's race?

RRDB must not become:

- automatic ◎ / ○ / ▲;
- a fixed numeric bonus;
- a standalone betting recommendation;
- a signal-count score.

The narrowed HV signal should be read as:

> despite a source finish of sixth or worse, the adjusted-time content sat in
> the operational Q85–Q90 band that reproduced as a useful next-start signal
> in the recent four-month check.

## 10. Newspaper/PWA presentation

Newspaper/PWA receives only matched target horses plus RRDB-generated short prose.

Canonical reader-facing phrases:

- `TIME_CLASS_PLUS1` -> `前走時計はクラス水準より上。`
- `FRONT_SURVIVE_GAP05` -> `前傾ラップ戦を前で受け、勝ち馬と僅差まで踏ん張った。`
- `REAR_HIGH_LAST3F90` -> `後傾ラップ戦も後方から上位の上がりは使った。`
- `HV02_Q85_Q90` -> `敗戦でもタイムは水準以上。`

When TIME_CLASS and HV02_Q85_Q90 coexist, do not repeat two near-synonymous
time sentences; keep the TIME_CLASS sentence.

Presentation policy remains:

- if the horse already has a RaceNote mark, keep that mark and make it tappable;
- if the horse has no RaceNote mark, display `注`;
- the modal shows the RRDB short comment;
- do not add a standalone RRDB column.

## 11. Evidence basis

The four-signal v0.3 cutover uses:

- 2024–2025 Historical OOS evidence for TIME_CLASS / FRONT / REAR;
- 2026-06〜09 HV fine-band exploratory comparison for narrowing the HV lane;
- the observed need to keep Newspaper/PWA recommendations sparse and
  reader-useful rather than returning every broad HV match.

The relevant HV comparison is documented in:

`docs/RaceReviewDB_202606_202609_HV_FineBand_Comparison_v0_1.md`

## 12. Legacy boundary

Historical-only assets include:

- broad HV01/HV02 recommendation output from v0.2;
- old Next-Watch S/A contract;
- `jrdb_next_watch_rules.py`;
- `RaceReviewDB_NextWatch_Operation_v0_1.md`.

They are not current operational recommendation output after the v0.3 cutover.

## 13. Canonical ownership

Code / contract / docs:

GitHub `main`.

Operational RRDB data:

stable Drive `RaceReviewDB_CURRENT.zip`.

Research artifacts remain evidence and reproduction sources; they do not
override the current serving contract.

## 14. Default output

Return matched horses in race / horse-number order unless a downstream Forecast
layer applies its own ranking.

Example:

```text
○○
- 上位クラス時計: class gap +1.3

△△
- 後傾差し逆行: 上がり98pct

□□
- 8着から補正タイムQ85_Q90
```

No S/A prefix. No ranking solely by matched signal count.

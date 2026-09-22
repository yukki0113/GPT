# KEIRIN Canonical Design v0.1

Date: 2026-09-23
Status: DESIGN FREEZE CANDIDATE
Scope: 2016-2025 Historical + future daily acquisition
Drive canonical root: `10_canonical/`

## 1. Design goal

競輪Canonicalの目的は、単にKEIRIN.JPのHTMLを表形式へ変換することではない。

将来の予想ロジックが、
- 個人の脚力
- 自力/追込などの戦法特性
- ライン構成とライン内位置
- ライン同士の力関係
- バンク適性
- 直近状態
- コメント/作戦
- オッズ
- 天候/風
- 選手同士の過去連携

へ拡張しても、Rawへ戻って全面再設計しなくてよいCanonicalを作る。

Canonicalには source facts と時間軸を保持し、モデル固有の指数や集約特徴量は原則 `30_analysis/` で生成する。

## 2. Core principle

### 2.1 PRE / POST physical separation

予想時点で利用できる情報と、レース後に初めて確定する情報を物理的に分離する。

- `pre/`: 発走前に利用可能だった事実
- `post/`: 着順・決まり手・配当等の結果
- `provenance/`: Rawとの対応、parser version、SHA、監査

学習時は原則 `pre/` のみをfeature sourceとし、`post/` はtarget/settlement専用とする。

### 2.2 Long format

選手1〜9を横持ちしない。

1レース7車/9車等の違い、ガールズ、将来の競走体系変更に対応するため、

- race = 1 row / race
- entry = 1 row / rider / race
- line member = 1 row / rider / line snapshot
- result = 1 row / rider / race

のlong formatを標準とする。

### 2.3 Temporal truth

Historicalで最も重要なのは「今の選手プロフィール」ではなく「そのレース時点の値」。

競走得点、級班、登録府県、脚質、直近4ヶ月成績等はrace-time snapshotとして保持する。

現在プロフィールを過去レースへjoinして埋めない。

各snapshot系tableは最低限、
- effective_asof
- source_updated_at
- acquired_at
- source_raw_sha256

を持つ。

### 2.4 Facts and inference separation

出典に掲載された事実と、GPT/ロジックが推定したものを混ぜない。

特にラインは、
- published / source-observed
- inferred
- manual-labelled

を明確に分ける。

推定ラインはCanonical Factへ上書きせず、`30_analysis/line_hypothesis/` 等へ保存する。

## 3. Why line is a first-class entity

通常の男子競輪では、ラインは単なるカテゴリーではなく「誰が誰の後ろを走るか」というレース内の関係構造。

予想上必要になるのは、
- ライン数
- 各ライン人数
- 自力型の先頭
- 番手
- 3番手以降
- 単騎
- 競り
- 同県/同地区/同期などの結び付き
- ライン先頭と番手の力量差
- ライン同士の先行力比較

である。

したがって `line="1-5-7"` の1文字列だけでは不十分。

またガールズ競輪はラインを前提としない。
将来の日次運用では男子でも国際ルール系競走があり得るため、raceごとにrulesetを持つ。

## 4. Canonical physical layout

```
10_canonical/
└─ v0_1/
   ├─ manifest/
   │  ├─ generation.json
   │  ├─ schema.json
   │  └─ coverage.json
   ├─ dimensions/
   │  ├─ rider_identity/
   │  └─ venue_config/
   ├─ pre/
   │  ├─ meet/
   │  ├─ race/
   │  ├─ entry/
   │  ├─ entry_form_snapshot/
   │  ├─ line_group/
   │  ├─ line_member/
   │  ├─ position_contest/
   │  ├─ rider_comment/
   │  ├─ weather_snapshot/
   │  └─ odds_snapshot/
   ├─ post/
   │  ├─ result/
   │  ├─ race_result/
   │  └─ payout/
   └─ provenance/
      ├─ source_asset/
      ├─ row_source_map/
      └─ parse_audit/
```

Parquet:
- ZSTD
- partition: `year=YYYY/month=MM` for race-sized fact families
- DuckDB read-first
- schema hash in generation manifest

## 5. Keys

### meet_key

Preferred:
`venue_code | meet_start_date`

If collision occurs:
`venue_code | meet_start_date | meet_sequence`

Do not use monthly discovery ordinal as permanent identity.

### race_key

`YYYYMMDD | venue_code | race_no`

Historical race date must be parsed from official returned data.
Do not infer by `meet_start + N days`.

### entry_key

`race_key | rider_id`

### line_snapshot_key

`race_key | line_snapshot_version`

### source_asset_key

provider + raw_sha256

## 6. Dimension tables

### 6.1 dimensions/rider_identity

Only stable identity-oriented fields.

Fields:
- rider_id
- rider_name
- rider_name_kana if available
- sex_category
- training_term
- birth_date if historically reliable
- identity_source
- first_seen_date
- last_seen_date

Do NOT put mutable race-time values here:
- current class
- current prefecture
- age
- competition score
- leg style

Those belong in PRE entry snapshot.

### 6.2 dimensions/venue_config

Bank configuration can change by renovation, so effective dating is required.

Fields:
- venue_code
- venue_name
- effective_from
- effective_to
- lap_length_m
- home_straight_m / deemed_straight_m
- max_cant_deg
- indoor_flag
- config_source

Prediction features such as 333/400/500-type suitability must be derived from this historical configuration.

## 7. PRE tables

### 7.1 pre/meet

1 row / meet.

Core fields:
- meet_key
- venue_code
- meet_start_date
- meet_end_date
- grade
- event_name
- scheduled_days
- actual_days
- meet_status
- source_updated_at
- source_raw_sha256

### 7.2 pre/race

1 row / race.

Core fields:
- race_key
- meet_key
- race_date
- venue_code
- race_no
- day_no
- day_label_raw
- scheduled_start_time
- race_label_raw
- class_category
- race_stage
- grade
- distance_m
- laps
- starters_scheduled
- competition_category
- race_ruleset
- cancellation_status
- source_updated_at
- source_raw_sha256

Suggested race_ruleset values:
- `standard_keirin_line`
- `girls_international_no_line`
- `advance_international_no_line`
- `other`
- `unknown`

Keep `race_label_raw` even after normalization.

### 7.3 pre/entry

1 row / rider / race.

This is the main prediction input snapshot.

Identity / draw:
- race_key
- rider_id
- car_no
- frame_no if applicable

Historical-at-race attributes:
- rider_name_at_race
- age_at_race
- registered_prefecture
- region
- training_term
- class_current
- class_previous if source provides
- leg_style_raw
- leg_style_norm
- gear_ratio if available

Strength / recent-form snapshot:
- competition_score
- win_rate
- top2_rate
- top3_rate
- first_count
- second_count
- third_count
- outside_count
- withdrawal_count
- disqualification_count
- start_count
- home_count
- back_count

Tactical result tendency displayed before race:
- kimarite_nige_count / rate
- kimarite_makuri_count / rate
- kimarite_sashi_count / rate
- kimarite_mark_count / rate

Temporal/provenance:
- effective_asof
- source_updated_at
- source_raw_sha256

Do not fill missing historical fields from the rider's current profile.

### 7.4 pre/entry_form_snapshot

Optional source-published recent form.

One row per prior-form item rather than `recent1...recent8` columns.

Fields:
- race_key
- rider_id
- lookback_rank
- prior_event_date
- prior_venue_code
- prior_grade
- prior_finish_summary_raw
- prior_back_marker
- linked_prior_race_key if resolvable

Our own rolling history features should mainly be recomputed from Canonical POST results.
This table preserves what the historical racecard itself displayed.

### 7.5 pre/line_group

1 row / line / snapshot.

Fields:
- line_snapshot_key
- race_key
- line_id
- line_order_display
- member_count
- head_rider_id
- line_status: standard / solo / contested / unknown
- source_kind: published / manual / inferred
- source_name
- confidence nullable
- effective_asof

Rule:
Only `source_kind=published` may be treated as source fact.
Inferred lines are not silently promoted to published fact.

### 7.6 pre/line_member

1 row / rider / line.

Fields:
- line_snapshot_key
- race_key
- line_id
- rider_id
- position_no
- role_norm

Suggested role_norm:
- head_self_power
- second_bante
- third
- fourth_plus
- solo
- unknown

Also preserve:
- role_raw
- relation_to_front_rider_id

### 7.7 pre/position_contest

For `競り` etc. A simple line order cannot represent multiple riders fighting for one wheel.

Fields:
- race_key
- target_rider_id
- target_position
- contender_rider_id
- contest_type
- source_kind
- effective_asof

This table can remain empty until a reliable source is available.

### 7.8 pre/rider_comment

Preserve text, do not reduce it to tags only.

Fields:
- race_key
- rider_id
- comment_text_raw
- source_kind
- effective_asof
- source_raw_sha256

NLP-derived tags such as
- 自力
- 前で
- 番手
- 任せる
- 単騎
- 競る
should live in analysis outputs, with model/parser version.

### 7.9 pre/weather_snapshot

Optional.

Fields:
- race_key
- snapshot_at
- weather
- temperature_c
- wind_speed_mps
- wind_direction
- precipitation
- track_condition_raw

Important:
For a previous-day prediction model, race-day observed weather after the prediction cutoff must not be used as training input.
Always keep snapshot timestamp.

### 7.10 pre/odds_snapshot

Optional and potentially large.

Fields:
- race_key
- bet_type
- selection_key
- odds
- popularity_rank
- snapshot_at
- is_final_preclose_snapshot

No odds row without timestamp.

## 8. POST tables

### 8.1 post/result

1 row / rider / race.

Fields:
- race_key
- rider_id
- car_no
- finish_order
- result_status
- finish_time if available
- margin_raw
- kimarite_raw
- home_marker
- back_marker
- start_marker
- penalty / disqualification fields if available
- source_raw_sha256

### 8.2 post/race_result

1 row / race.

Fields:
- race_key
- winner_rider_id
- winner_car_no
- winning_kimarite
- race_completed_flag
- cancellation/refund state
- result_updated_at

### 8.3 post/payout

1 row / bet combination.

Fields:
- race_key
- bet_type
- selection_key
- payout_yen
- popularity_rank
- refund_flag

Used for settlement / ROI only.

## 9. Current Raw -> Canonical stages

The current 2016-2025 8,464-meet Raw is valuable but is a meet-level foundation, not yet the final prediction-grade detail dataset.

### Stage A: Core Canonical from existing Raw

Without new HTTP requests, parse:
- meet
- actual race days
- race numbers
- race labels / class blocks
- race detail tokens
- cancellation/event flags
- available selected-race identity data
- provenance

Output:
- `pre/meet`
- `pre/race`
- initial `provenance/*`

This becomes the race universe and exact acquisition index.

### Stage B: Prediction Detail source probe

Before bulk detail acquisition:
1. Use one Historical race token.
2. Identify the official detail transition used by KEIRIN.JP.
3. Confirm historical-at-race fields.
4. Confirm fields needed for:
   - competition_score
   - class/style
   - decisive-method counts
   - H/B counts
   - recent results
   - result
5. Check whether comments or published line formation exist.
6. Audit 2016 / 2020 / 2025 representative races.

Do not start mass per-race retrieval until this probe passes.

### Stage C: Detail Raw acquisition

Only after Stage B.

Rate-limit separately from meet collection.
Use:
- immutable Raw
- request manifest
- no-refetch cache
- year/month checkpoint
- fail-close on access restriction

If line/comments are not provided by KEIRIN.JP, do not invent them during Canonical parsing.

### Stage D: Prediction Canonical

Populate:
- pre/entry
- pre/entry_form_snapshot
- post/result
- post/payout

Populate line/comment tables only when a reliable approved source or explicit inference pipeline exists.

## 10. Prediction feature roadmap

Canonical should support the following feature families without schema redesign.

### Phase P0: Individual baseline

No line required.

Features:
- competition score rank / gap
- class
- recent win/top2/top3
- H/B counts
- escape/makuri/sashi/mark tendency
- recent result trend
- venue / bank type
- race stage

Goal:
Establish a reproducible baseline before adding complex tactical information.

### Phase P1: Self-power / initiative

Estimate who is likely to create the race.

Derived candidates:
- self_power_index
- B rate
- H rate
- nige+makuri share
- field self-power count
- single_self_power_flag

### Phase P2: Line-aware model

Requires published or sufficiently audited inferred line structure.

Derived candidates:
- num_lines
- line_length
- line_head_power
- bante_power
- line_score_sum / mean / max
- line_score_gap_vs_best_other
- same_prefecture_count
- same_region_count
- same_training_term_count
- rider_pair_same_line_history
- head_bante_pair_success
- contested_bante_flag
- solo_flag
- field split type (2-line / 3-line / 4-line)

Important:
Pair-history and line-strength aggregates belong in feature marts, not Canonical facts.

### Phase P3: Venue fit

Derived from venue_config + historical results.

Candidates:
- rider performance by lap length
- rider performance by straight-length bucket
- rider x venue
- tactic x venue
- line position x venue
- wind interaction when timestamp-valid

### Phase P4: Strategy / comment NLP

Requires comment text.

Examples:
- 自力宣言
- 前で
- ○○に任せる
- 番手
- 競り
- 単騎
- 状態/疲労 wording

Store the original comment in Canonical; derived tags/versioned embeddings in analysis.

### Phase P5: Market-aware model

Optional.
Keep both:
- pure forecast model without odds
- value model using timestamp-valid odds

Do not let final/post-race odds leak into a previous-day model.

## 11. Leakage rules

Hard rules:

1. POST tables cannot be joined into feature generation except as lagged history where the prior race occurred before prediction cutoff.
2. Current rider profile may not fill historical entry snapshot.
3. Current class/prefecture/style may not overwrite historical values.
4. Race-day weather after prediction cutoff is unavailable to a previous-day model.
5. Odds require snapshot timestamp.
6. Same-meet earlier-day results may be used only if they were already known at prediction cutoff.
7. Any feature must be reproducible from data with `available_at <= prediction_asof`.

Recommended default prediction cutoff for research:
- `previous_day_21:00 JST`

Keep cutoff configurable.

## 12. Audit gates

Every Canonical generation must report:

### Universe
- meet count
- race count
- entry count
- result count
- unique rider count

### Key integrity
- duplicate meet_key
- duplicate race_key
- duplicate entry_key
- orphan entry/result
- race date outside meet actual day list

### PRE / POST
- PRE rows containing prohibited result fields = 0
- POST result without PRE race = 0

### Coverage
By year:
- races with entry details
- races with competition score
- races with style
- races with B count
- races with result
- races with payout
- races with published line
- races with comments

Never report line coverage as 100% simply because the line table exists.

### Temporal
- snapshot after race start
- current-profile leakage
- impossible prior-race ordering

## 13. Generation manifest

Example fields:

```json
{
  "generation": "KEIRIN_CANON_V0_1_YYYYMMDD_HHMM_<sha>",
  "schema_version": "0.1",
  "source_range": "2016-2025",
  "source_provider": "keirin.jp",
  "source_policy": "personal_research_approved",
  "raw_drive_root": "...",
  "parser_commit": "...",
  "schema_hash": "...",
  "pre_post_separated": true,
  "line_fact_policy": "published_only_in_canonical",
  "status": "pass|partial|fail"
}
```

## 14. Recommended implementation order

1. Implement Stage A Core parser using existing 8,464-meet Raw only.
2. Produce race universe and exact race counts.
3. Run duplicate/date/cancellation audits.
4. Probe one official Historical race-detail route.
5. Decide detail acquisition contract and exact request volume before bulk access.
6. Acquire prediction-detail Raw conservatively.
7. Populate pre/entry + post/result.
8. Build P0 baseline model.
9. Only then solve line acquisition/inference and add P2.

This order prevents the project from blocking on line data before a usable baseline exists.

## 15. Design decision summary

- Canonical is model-independent.
- PRE / POST are physically separated.
- Race and rider facts use long format.
- Historical-at-race values are mandatory.
- Line is a relational entity, not a text column.
- Published line facts and inferred lines are kept separate.
- Race ruleset is explicit because not every race uses line tactics.
- Venue configuration is effective-dated.
- Comments are preserved as raw text for future NLP.
- Odds/weather require timestamps.
- Engineered prediction features live in `30_analysis`.
- Current 10-year meet Raw is the immutable foundation; detail acquisition is an additive next stage, not a replacement.

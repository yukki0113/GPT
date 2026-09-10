# Eval Phase2 JRDB Training Features v0.1

## 1. 目的

Eval Phase2研究で、Eval値と市場評価のズレを説明する調教・仕上状態候補を、開催前PACIのJRDB CHA/CYBから再現可能に取得する。

固定長BYTE位置はEval側に持たない。CHA/CYBの固定長parseは `jrdb_raw.Parser`、既存の型・名称正規化は `jrdb_index_base_adapter.parse_cha / parse_cyb` を正本として再利用する。

対象実装:

```text
horse-racing/eval/src/build_phase2_jrdb_training_features.py
```

## 2. 結合方針

KYI `race_horse_key` を対象馬集合の正本とする。

```text
KYI 1頭
  ├─ LEFT JOIN CHA
  └─ LEFT JOIN CYB
```

CHA/CYBは欠損・未提供があり得るため、存在しない馬を除外しない。`cha_status` / `cyb_status` を `MATCHED` または `MISSING` として保持する。

CHA/CYBにKYI対象馬集合外の行が存在する場合は推測結合せず構造エラーとする。

## 3. CHA 本追切層

CHAは本追切の実測・標準化情報として扱う。

保持項目:

```text
cha_training_date
cha_weekday
cha_workout_count
cha_course_code
cha_effort_code
cha_chase_state_code
cha_rider_type_code
cha_furlong_count
cha_first_segment_sec
cha_middle_segment_sec
cha_final_segment_sec
cha_first_segment_index
cha_middle_segment_index
cha_final_segment_index
cha_workout_index
cha_pair_result_code
cha_pair_effort_code
cha_pair_age
cha_pair_class_code
```

主な既知コード:

- `cha_effort_code`: 1=一杯, 2=強目, 3=馬なり
- `cha_rider_type_code`: 1=助手, 2=調教師, 3=本番騎手, 4=調教騎手, 5=見習
- `cha_pair_result_code`: 1=先着, 2=同入, 3=遅れ
- `cha_chase_state_code`: JRDB追い状態コード表を参照
- `cha_course_code`: JRDB調教コースコード表を参照

MVPではコード表をEval側へ複製せずraw codeを保持する。必要な表示ラベルは研究表示層でJRDB正本コード表から解決する。

## 4. CYB 調教分析・仕上層

CYBは調教時計の加工値と仕上過程を表す別レイヤーとして扱う。

保持項目:

```text
cyb_training_type_code
cyb_training_course_type_code
cyb_used_slope
cyb_used_wood
cyb_used_dirt
cyb_used_turf
cyb_used_pool
cyb_used_jump
cyb_used_polytrack
cyb_training_distance_code
cyb_training_focus_code
cyb_workout_index
cyb_finish_index
cyb_training_volume_code
cyb_finish_change_code
cyb_training_evaluation_code
cyb_week_ago_workout_index
cyb_week_ago_course_code
```

意味:

- `cyb_workout_index`: 追切指数。調教時計を指数化した値
- `cyb_finish_index`: 仕上指数。仕上状態を指数化した値
- `cyb_training_volume_code`: 調教量評価 A/B/C/D
- `cyb_finish_change_code`: 仕上指数変化
- `cyb_training_evaluation_code`: 調教評価 1=◎, 2=○, 3=△
- `cyb_week_ago_workout_index`: 一週前追切指数
- course利用フラグ: 01=有り / 00=無しを既存adapterで0/1へ正規化

`training_type_code` 等、別説明資料が必要なカテゴリは意味を推測せずコードのまま保持する。

## 5. 3種類の「調教系指数」を混同しない

Phase2では以下を別概念として保持する。

```text
KYI training_index        = 調教指数（JRDB/専門紙の判断系）
CHA cha_workout_index     = 本追切レコード側の総合時計指数
CYB cyb_workout_index     = 調教分析側の追切指数
```

CHAとCYBの追切指数が同値であることを前提にしない。

Adapterは `workout_index_relation` を出す。

```text
BOTH_MISSING
CHA_ONLY
CYB_ONLY
MATCH
MISMATCH
```

値が異なる場合も片方へ統合せず、両値を保持して監査可能にする。

## 6. リーケージ

入力は開催前PACIのKYI/CHA/CYBのみ。

```text
source_availability_class = PRE_RACE
```

対象レースSED、確定着順、確定人気、確定オッズ、払戻は参照しない。

## 7. Phase2研究での初期用途

これらは購入ルールとして事前に良し悪しを決めない。

第一用途は、

```text
Eval高評価
× 市場評価低下
```

の理由を説明できるかのDiscoveryとする。

例:

- 長期休養 × 仕上指数
- KYI調教矢印 × CYB仕上指数
- 本追切指数 × 一週前追切指数
- 調教量評価 × 休養日数
- CHA/CYB指数不一致
- ポリトラック利用有無

同一Discovery標本から良いセルだけを選んでForward条件へ後付けしない。

## 8. 次段階

次はKYIの前走1競走成績キーを使い、開催前に提供されるZEDまたはannual Rawの対応SEDから、前走条件をexact-linkで付与する。

候補:

```text
前走日
前走距離
前走芝ダ
前走馬場状態
前走クラスコード
距離増減
芝ダ変更
```

現在クラスと前走クラスから「昇級/降級」を意味変換する処理は、コード順序・格上挑戦等の定義を別途固定してから行う。

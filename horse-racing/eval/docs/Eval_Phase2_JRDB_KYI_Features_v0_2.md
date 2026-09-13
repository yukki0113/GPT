# Eval Phase2 JRDB KYI Features v0.2

Status: CURRENT  
Implementation: `horse-racing/eval/src/build_phase2_jrdb_kyi_features.py`  
Implementation schema version: `0.2.0`

## 1. 目的

Eval Phase2研究で、Eval値と市場評価のズレを説明する開催前特徴量を、JRDB PACIのBAC/KYIから再現可能かつリーケージを避けて取得する。

固定長BYTE位置はEval側に再定義しない。正本はJRDB common raw parser / adapterであり、本moduleは既にparseされた値をPhase2研究用schemaへ投影するconsumerとする。

```text
horse-racing/eval/src/build_phase2_jrdb_kyi_features.py
```

入力は開催前 `PACIyymmdd.zip`。current-race SED、確定着順、確定人気、確定オッズ、払戻等の結果時点sourceは読まない。

```text
source_availability_class = PRE_RACE
```

## 2. Identity / join

BACをrace identityの正本としてKYIを解決する。

主要identity:

```text
race_date
venue
venue_code
race_no
horse_no
race_key
race_horse_key
horse_name
```

Phase2外部結合では原則:

```text
race_date + venue + race_no + horse_no
```

をCanonical Keyとする。Phase2 component内部では `race_horse_key` を1頭1行identityとして利用する。

KYI `race_key` がBACに存在しない、`race_horse_key` が空、同一 `race_horse_key` が重複する等は推測補完せずstructure errorとする。

## 3. v0.1から継続する特徴量

### 3.1 枠・脚質

```text
frame_no
running_style_code
running_style_label
```

`running_style_code` の既知label:

```text
1 逃げ
2 先行
3 差し
4 追込
5 好位差し
6 自在
```

### 3.2 KYI調教判断

```text
training_index
training_arrow_code
training_arrow_label
```

`training_arrow_code`:

```text
1 デキ抜群
2 上昇
3 平行線
4 やや下降気味
5 デキ落ち
```

この `training_index` はCHA/CYBの追切指数と別概念。後段で値が同じでも統合しない。

### 3.3 適性

```text
heavy_track_fit_code
heavy_track_fit_label
turf_fit_code
turf_fit_label
dirt_fit_code
dirt_fit_label
```

既知3段階label:

```text
1 ◎
2 ○
3 △
```

`heavy_track_fit` は馬自身の道悪適性であり、今走の確定実馬場状態ではない。

### 3.4 前走key / 休養

```text
prev_result_key_1
prev_race_key_1
previous_race_date
layoff_days
layoff_status
rotation_interval
```

`layoff_days` はKYI `previous[0].result_key` 末尾8桁の前走日とBAC今走日との差で算出する。

```text
layoff_days = 今走開催日 - 前走日
```

`rotation_interval` はJRDBの別概念なので休養日数の代用にしない。

`layoff_status`:

```text
OK
DEBUT_NO_PREVIOUS
INVALID_PREVIOUS_KEY
NON_POSITIVE_INTERVAL
```

### 3.5 休養理由 / 入厩

```text
rest_reason_code
rest_reason_label
stable_run_no
stable_entry_date_raw
stable_entry_date
stable_days_before
```

休養理由labelは共通JRDB code tableを使用する。空欄を「理由なし」と推測しない。

不正な入厩日はrawを保持し、正規化列を空欄にしてaudit件数へ残す。

### 3.6 枠確定馬体重

```text
body_weight_pre_kg
body_weight_change_pre_kg
```

結果時SEDの馬体重とは別列・別時点。PACI内で実際に存在する場合だけ使用し、欠損を0補完しない。

## 4. v0.2追加特徴量

v0.2ではJRDB common parserが公開する以下のKYI事前fieldを追加する。Eval側で固定長位置や独自意味を再定義しない。

### 4.1 厩舎系判断

```text
stable_index
stable_evaluation_code
stable_evaluation_label
```

`stable_evaluation_code` は既存共通mappingを使用する。

```text
1 超強気
2 強気
3 現状維持
4 弱気
```

`stable_index` はparserが返す原値を保持し、Eval側で別指数へ意味変換しない。

### 4.2 予想ペース

```text
forecast_pace_code
forecast_pace_label
```

既知mapping:

```text
H ハイ
M 平均
S スロー
```

これは開催前KYI上の予想情報であり、レース後に確定する実ペースではない。

### 4.3 展開予測 index / rank

```text
expected_front_index
expected_pace_index
expected_late_index
expected_position_index
expected_front_rank
expected_pace_rank
expected_late_rank
expected_position_rank
```

これらはcommon parserの `pace_indices` / `pace_ranks` が返す開催前KYI値をそのまま保持する。

Eval側では、field名を超える新しい意味・閾値・優劣ルールをこのadapter内で定義しない。研究上の派生カテゴリや閾値はDiscovery側で別途定義し、同一標本から後付けで正式条件へ昇格させない。

### 4.4 スタート / 出遅れ関連原値

```text
start_index
late_break_rate
```

common parserが返す開催前KYI値をそのまま保持する。欠損を0として補完しない。

## 5. 出力契約

v0.2.0実装の1頭1行出力列は次。

```text
race_date
venue
venue_code
race_no
horse_no
race_key
race_horse_key
horse_name
frame_no
running_style_code
running_style_label
training_index
training_arrow_code
training_arrow_label
stable_index
stable_evaluation_code
stable_evaluation_label
heavy_track_fit_code
heavy_track_fit_label
turf_fit_code
turf_fit_label
dirt_fit_code
dirt_fit_label
forecast_pace_code
forecast_pace_label
expected_front_index
expected_pace_index
expected_late_index
expected_position_index
expected_front_rank
expected_pace_rank
expected_late_rank
expected_position_rank
start_index
late_break_rate
prev_result_key_1
prev_race_key_1
previous_race_date
layoff_days
layoff_status
rotation_interval
rest_reason_code
rest_reason_label
stable_run_no
stable_entry_date_raw
stable_entry_date
stable_days_before
body_weight_pre_kg
body_weight_change_pre_kg
source_availability_class
source_file
source_member
jrdb_raw_version
```

## 6. Audit / fail-closed

moduleは少なくとも次をauditする。

- `race_count`
- `runner_rows`
- duplicate `race_horse_key`
- invalid stable-entry dates
- `layoff_status` counts
- JRDB raw parserのrecord-length errors
- `source_availability_class = PRE_RACE`
- `jrdb_raw_version`

record length error、BAC/KYI identity不整合、unsupported venue、duplicate identity等は推測で続行しない。

## 7. Leakage boundary

全出力のsourceは今走開催前PACI BAC/KYI。

使用禁止:

- current-race SED
- 今走確定着順
- 今走確定人気
- 今走確定オッズ
- 今走払戻
- 結果を知った後に作る後付けfield

前走条件を利用する場合は別module `build_phase2_jrdb_previous_features.py` がKYI previous result keyとPACI ZEDをexact-linkする。

調教実測/仕上を利用する場合は別module `build_phase2_jrdb_training_features.py` がKYI identity setへCHA/CYBをLEFT JOINする。

## 8. 研究上の扱い

これらのfieldは、まずEval高評価と市場評価のズレを説明できるかを見るDiscovery材料とする。

- 休養 × 調教/厩舎判断
- 予想ペース × 脚質/展開index
- スタート関連 × 想定位置
- 適性 × 当日条件
- 事前馬体重 × 休養/仕上

良いセル・閾値が見つかっても同一Discovery標本だけで正式Forward条件へ追加しない。

## 9. Version policy

この文書はimplementation `VERSION = 0.2.0` に対応する。

sourceのVERSION / OUTPUT_COLUMNSと本書が不一致になった場合、sourceを推測で古いdocumentへ合わせず、実装・tests・docsを監査し、正しいcurrent contractへ文書を更新する。

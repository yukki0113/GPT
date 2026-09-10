# Eval Phase2 JRDB KYI Features v0.1

## 1. 目的

Eval Phase2研究で、Eval値と市場評価のズレを説明する「当日リスク」候補を、JRDBの開催前KYIデータから再現可能に取得する。

固定長BYTE位置はEval側に再定義しない。正本は `horse-racing/jrdb/src/jrdb_raw.py::Parser` とし、本AdapterはCommon Raw Readerの返却値をPhase2研究用schemaへ投影するだけとする。

対象実装:

```text
horse-racing/eval/src/build_phase2_jrdb_kyi_features.py
```

入力は開催前 `PACIyymmdd.zip`。SED、確定着順、確定人気、確定オッズ、払戻等の結果系データは読まない。

## 2. 今回固定する特徴量

### 2.1 休養日数

`休養日数` はKYI `rotation_interval` を転用しない。

KYIの `previous[0].result_key` は `血統登録番号8BYTE + YYYYMMDD8BYTE` なので、末尾8桁の前走日と今走BAC開催日の暦日差を計算する。

```text
layoff_days = 今走開催日 - 前走日
```

初出走等で前走キーがない場合は `0` にせず空欄とする。

`layoff_status`:

```text
OK
DEBUT_NO_PREVIOUS
INVALID_PREVIOUS_KEY
NON_POSITIVE_INTERVAL
```

JRDB `rotation_interval` は別列に原値保持する。固定長仕様上、これは「間に金曜日が入っている数」で決定される値であり、暦日休養日数とは意味が異なる。

### 2.2 脚質

KYI `running_style_code` を使用する。

```text
1 逃げ
2 先行
3 差し
4 追込
5 好位差し
6 自在
```

出力:

```text
running_style_code
running_style_label
```

### 2.3 調教指数

KYI `training_index` を使用する。

これはCYBの追切指数とは別物。JRDB/専門紙の判断系シグナルとして保持し、追切時計系特徴量と混ぜない。

### 2.4 調教矢印

KYI `training_arrow_code` を使用する。

```text
1 デキ抜群
2 上昇
3 平行線
4 やや下降気味
5 デキ落ち
```

`improvement_code`（上昇度）とは別概念として保持する。

### 2.5 重馬場適性

KYI `heavy_track_fit_code` を使用する。

```text
1 ◎
2 ○
3 △
```

これは「当日の馬場状態」ではなく、馬自身の道悪適性。実馬場状態とは別列で扱い、研究時に交互作用を見る。

### 2.6 芝・ダート適性

KYI `turf_fit_code` / `dirt_fit_code` を使用する。

```text
1 ◎
2 ○
3 △
```

距離適性とは独立した特徴量として保持する。

### 2.7 枠番

KYI `frame_no` を使用する。1～8の原値を保持し、内・中・外などの後付けカテゴリはDiscovery側で必要になった場合のみ派生する。

### 2.8 JRDBローテーション

KYI `rotation_interval` を原値保持する。

休養日数と同一視しない。

### 2.9 休養理由

KYI `rest_reason_code` を使用し、既存JRDBコード表のラベルを付与する。

例:

```text
01 放牧
02 放牧（故障・骨折等）
03 放牧（不安・ソエ等）
04 放牧（病気）
05 放牧（再審査）
06 放牧（出走停止）
07 放牧（手術）
11 調整
12 調整（故障・骨折等）
13 調整（不安・ソエ等）
14 調整（病気）
15 調整（再審査）
16 調整（出走停止）
21 その他
```

空欄は「理由なし」と解釈せずデータ無しとして空欄保持する。

### 2.10 入厩関連

KYIから以下を原値保持する。

```text
stable_run_no
stable_entry_date_raw
stable_entry_date
stable_days_before
```

意味:

- `stable_run_no`: 入厩後何走目か
- `stable_entry_date`: 入厩年月日
- `stable_days_before`: レース日から遡った入厩日数（今走前に入厩の場合）

日付が不正な場合は推測補完せず、正規化列を空欄にしてauditへ件数を残す。

### 2.11 枠確定馬体重

KYIから以下を保持する。

```text
body_weight_pre_kg
body_weight_change_pre_kg
```

固定長仕様上の名称は「枠確定馬体重」「枠確定馬体重増減」。SEDの結果時 `body_weight_kg / body_weight_change_kg` とは別列として扱う。

Forwardでは、対象時点のPACIに実際に値が存在する場合だけ利用する。欠損を0補完しない。

## 3. 出力契約

Phase2 Adapterは1頭1行で以下を出す。

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
heavy_track_fit_code
heavy_track_fit_label
turf_fit_code
turf_fit_label
dirt_fit_code
dirt_fit_label
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

結合先では `race_date + venue + race_no + horse_no` をCanonical Keyとして使用する。

## 4. 利用時点とリーケージ

全項目のsourceはPACI BAC/KYIのみ。

```text
source_availability_class = PRE_RACE
```

ただし、PACI内の個別フィールドが空欄の場合は、その時点で利用可能だったと推測して埋めない。特に枠確定馬体重は実運用時点の取得状況をそのまま尊重する。

## 5. Phase2シートへの対応

既存列への対応:

```text
Phase2_全馬研究.AH 休養日数 <- layoff_days
Phase2_全馬研究.AK 調教指数 <- training_index
Phase2_全馬研究.AL 脚質     <- running_style_label
```

その他の項目は、Phase2研究列を拡張する際にコード列とラベル列を区別して追加する。

SED由来の馬体重/増減をKYIの枠確定馬体重で上書きしない。

## 6. 次段階

KYI層の取得率・実値監査後に、別レイヤーとして以下を追加する。

```text
CHA: 本追切日、コース、強さ、時計、追切指数、併せ情報
CYB: 追切指数、仕上指数、調教量、調教タイプ、一週前追切指数
過去SED: 前走距離、前走surface、前走馬場、クラス等
```

KYIの `training_index` とCYBの `training_index` は同名でも意味が異なるため、後者はPhase2上で「追切指数」として別名管理する。

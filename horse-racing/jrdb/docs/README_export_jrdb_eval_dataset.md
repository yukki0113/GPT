# JRDB Raw Eval Dataset Exporter

`export_jrdb_eval_dataset.py` は、**Analysis Lite / Core SQLiteへ依存せず**、JRDB RawだけからEval表検証用の1レース1行CSVを生成する統合Exporterです。

## 1. 設計方針

Eval用途の正本入力はJRDB Rawに一本化します。

```text
JRDB Raw
  ├ BAC  レース条件
  └ SED  確定馬場状態 + BACとの整合確認
        ↓
export_jrdb_eval_dataset.py
        ↓
Eval専用CSV（1レース1行）
```

- Analysis Liteのschema変更・再生成はしない
- Core SQLiteのschema変更・再生成はしない
- BAC固定長解析は `export_jrdb_eval_race_conditions.py` の共通関数を再利用する
- Eval側の外部結合契約は `race_date + venue_code + race_no`
- 将来KYI / CHA / CYB等を追加しても、レース単位CSV契約を不用意に変更しない

## 2. 入力Raw

認識対象:

```text
BAC_YYYY.zip
SED_YYYY.zip
BACyymmdd.zip
SEDyymmdd.zip
PACIyymmdd.zip   # ZIP内BACを利用
BACyymmdd.txt
SEDyymmdd.txt
```

`--raw` にファイルまたはディレクトリを複数指定できます。ディレクトリは再帰探索します。

## 3. 出力列

### 生データ列

| 列 | TYPE | 取得元 | JRDB項目 |
|---|---|---|---|
| race_date | TEXT | BAC | 年月日 |
| venue_code | TEXT | BAC | レースキー 場コード |
| race_no | INTEGER | BAC | レースキー R |
| race_name | TEXT | BAC | レース名 |
| race_type_code | TEXT | BAC | 種別 |
| race_condition_code | TEXT | BAC | 条件 |
| race_symbol_code | TEXT | BAC | 記号 |
| weight_condition_code | TEXT | BAC | 重量 |
| grade_code | TEXT | BAC | グレード |
| track_type | TEXT | BAC | 芝ダ障害コード |
| distance | INTEGER | BAC | 距離 |
| track_condition_code | TEXT | SED | 馬場状態 |
| declared_field_size | INTEGER | BAC | 頭数 |
| turn_direction_code | TEXT | BAC | 右左 |
| inner_outer_code | TEXT | BAC | 内外 |
| course_code | TEXT | BAC | コース |
| event_region_code | TEXT | BAC | 開催区分 |

SEDにも多くの同一レース条件が収録されるため、統合時にBACとSEDの共通項目を比較します。相違があれば推測で採用せずエラー終了します。

### 表示用派生列

```text
venue_name
track_label
class_label
grade_label
track_condition_label
race_type_label
sex_condition_label
is_filly_only
weight_condition_label
turn_direction_label
inner_outer_label
course_label
```

生コードは必ず残し、ラベルは補助列として追加します。

## 4. BAC固定長位置

BACは176 BYTE。相対位置はJRDB仕様書の1始まり表記です。

```text
場コード             1 / 2BYTE
R                    7 / 2BYTE
年月日               9 / 8BYTE
距離                21 / 4BYTE
芝ダ障害コード       25 / 1BYTE
右左                26 / 1BYTE
内外                27 / 1BYTE
種別                28 / 2BYTE
条件                30 / 2BYTE
記号                32 / 3BYTE
重量                35 / 1BYTE
グレード            36 / 1BYTE
レース名            37 / 50BYTE
頭数                95 / 2BYTE
コース              97 / 1BYTE
開催区分            98 / 1BYTE
```

## 5. SED固定長位置

SEDは376 BYTEの馬単位データです。同一レースの各馬レコードからレース共通部を抽出し、完全一致することを確認して1レースへ集約します。

```text
場コード              1 / 2BYTE
R                     7 / 2BYTE
年月日               19 / 8BYTE
距離                 63 / 4BYTE
芝ダ障害コード       67 / 1BYTE
右左                 68 / 1BYTE
内外                 69 / 1BYTE
馬場状態             70 / 2BYTE
種別                 72 / 2BYTE
条件                 74 / 2BYTE
記号                 76 / 3BYTE
重量                 79 / 1BYTE
グレード             80 / 1BYTE
レース名             81 / 50BYTE
頭数                131 / 2BYTE
```

## 6. 結合キー

```text
race_date + venue_code + race_no
```

例:

```text
2025-08-24 + 04 + 11
```

JRDB内部の回・日をEval側へ露出させません。

## 7. 期間指定

```bash
python export_jrdb_eval_dataset.py \
  --raw /path/to/jrdb/raw \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --output eval_jrdb_2025.csv
```

開始・終了日は両端を含みます。

## 8. 対象レース一覧指定

```csv
race_date,venue_code,race_no
2025-08-24,04,11
2025-08-24,01,11
```

```bash
python export_jrdb_eval_dataset.py \
  --raw /path/to/jrdb/raw \
  --targets-csv eval_targets.csv \
  --fail-on-missing-target \
  --output eval_jrdb_selected.csv
```

`race_date` は `YYYY-MM-DD` / `YYYYMMDD`、`venue_code` は `4` / `04` の双方を受け付けます。

期間と対象一覧を同時に指定した場合はAND条件です。

## 9. 未確定SED

Eval検証は原則として確定済みレースを対象とするため、BACに対応するSEDが無い場合はデフォルトでエラーにします。

開催前Raw等を確認したい場合のみ:

```bash
--allow-missing-sed
```

を指定できます。この場合 `track_condition_code` / `track_condition_label` は空欄です。

## 10. コード変換

### 場コード

```text
01 札幌 / 02 函館 / 03 福島 / 04 新潟 / 05 東京
06 中山 / 07 中京 / 08 京都 / 09 阪神 / 10 小倉
```

### 芝ダ障害

```text
1 芝
2 ダート
3 障害
```

### 種別

```text
11 2歳
12 3歳
13 3歳以上
14 4歳以上
20 障害
99 その他
```

### 条件

```text
A1 新馬
A2 未出走
A3 未勝利
04/05 1勝クラス
08/09/10 2勝クラス
15/16 3勝クラス
OP オープン
```

### グレード

```text
1 G1
2 G2
3 G3
4 重賞
5 特別
6 L
```

空欄は通常競走等として空欄のまま保持します。

### 馬場状態

```text
10/11/12 良
20/21/22 稍重
30/31/32 重
40/41/42 不良
```

JRDBの速/遅区分を生コードに残し、表示ラベルではJRAの4区分へまとめます。

### 記号と牝馬限定

`race_symbol_code` は3桁。2桁目が性別条件です。

```text
0 指定なし
1 牡馬限定
2 牝馬限定
3 牡・せん馬限定
4 牡・牝馬限定
```

`is_filly_only` は2桁目が `2` のとき `1`、それ以外は `0`。

### 重量

```text
1 ハンデ
2 別定
3 馬齢
4 定量
```

### 右左 / 内外 / コース

```text
右左: 1 右 / 2 左 / 3 直 / 9 他
内外: 1 通常(内) / 2 外 / 3 直ダ / 9 他
コース: 1 A / 2 A1 / 3 A2 / 4 B / 5 C / 6 D
```

## 11. 整合性ポリシー

以下では推測補完しません。

- 同一TYPE内で同一 `race_date + venue_code + race_no` のレース共通情報が食い違う
- BACとSEDの共通レース条件が食い違う
- SEDだけ存在しBACが無い
- デフォルト設定でBACに対応するSEDが無い

いずれもエラー終了し、対象キーを表示します。

同一内容のRawが複数ソースに重複しているだけならcollapseします。

## 12. 依存関係

Python標準ライブラリのみ。外部pip依存はありません。

`export_jrdb_eval_dataset.py` と `export_jrdb_eval_race_conditions.py` は同じ `src/` ディレクトリに配置してください。

## 13. 将来の馬単位拡張

レース単位CSVは維持し、必要になった時点で別モードまたは別Exporterとして以下を追加する想定です。

```text
KYI: 騎手、枠番、馬番、脚質、距離適性、前走キー、斤量、馬体重等
SED: 確定人気/オッズ、着順、通過順、実馬体重等
CYB/CHA: 調教・追い切り
```

Eval側のレース結合キーは引き続き `race_date + venue_code + race_no` とします。

## 14. 別プロジェクト向け最小契約

入力:

```text
JRDB Raw BAC + SED
```

出力:

```text
UTF-8 BOM付きCSV
1レース1行
```

キー:

```text
race_date + venue_code + race_no
```

Eval台帳側が場名を持つ場合は、JRDB場コードへ変換してから結合してください。

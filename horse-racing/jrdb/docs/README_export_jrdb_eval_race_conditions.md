# JRDB BAC Eval Race Conditions Exporter

`export_jrdb_eval_race_conditions.py` は、**JRDB Analysis Liteを変更せず**、
JRDB Raw `BAC`（番組データ）からEval表検証用のレース条件CSVを生成する独立ツールです。

## 1. 目的

Eval台帳の

```text
開催日 + 場 + R
```

と結合できる、1レース1行の補助データを作ります。

Analysis Liteは別用途の軽量分析基盤としてそのまま維持し、このツールはRaw BACから必要なレース条件だけを都度または期間一括で抽出します。

## 2. 出力CSV

固定12列です。

```text
race_date
venue_code
race_no
race_name
race_type_code
race_symbol_code
weight_condition_code
declared_field_size
turn_direction_code
inner_outer_code
course_code
event_region_code
```

例:

```csv
race_date,venue_code,race_no,race_name,race_type_code,race_symbol_code,weight_condition_code,declared_field_size,turn_direction_code,inner_outer_code,course_code,event_region_code
2025-08-24,04,11,新潟２歳ステークス,11,500,3,10,2,1,1,3
```

上記値はフォーマット例です。実値は必ずRaw BACから生成してください。

## 3. Rawの取得元

すべて `BAC` 1レコードから取得します。

| 出力列 | BAC項目 | 相対位置 | BYTE | 備考 |
|---|---|---:|---:|---|
| `race_date` | 年月日 | 9 | 8 | YYYYMMDD → YYYY-MM-DD |
| `venue_code` | レースキー 場コード | 1 | 2 | 01～10がJRA |
| `race_no` | レースキー R | 7 | 2 | 整数化 |
| `race_name` | レース名 | 37 | 50 | CP932、trim |
| `race_type_code` | 種別 | 28 | 2 | JRDBコード |
| `race_symbol_code` | 記号 | 32 | 3 | 3桁を文字列保持 |
| `weight_condition_code` | 重量 | 35 | 1 | JRDBコード |
| `declared_field_size` | 頭数 | 95 | 2 | 整数化 |
| `turn_direction_code` | 右左 | 26 | 1 | 右/左/直/他 |
| `inner_outer_code` | 内外 | 27 | 1 | 内/外/直ダ/他 |
| `course_code` | コース | 97 | 1 | A/A1/A2/B/C/D |
| `event_region_code` | 開催区分 | 98 | 1 | 関東/関西/ローカル |

Pythonのoffsetは0始まりなので、仕様書の相対位置から1を引いて実装しています。

## 4. Eval結合キー

BACにはレースキーとは別に、開催年月日が `YYYYMMDD` で格納されています。

そのためEval側ではJRDBの「回」「日」を復元せず、

```text
race_date + venue_code + race_no
```

を結合キーにします。

例:

```text
2025-08-24 + 04 + 11
```

内部JRDBの8BYTE `race_key` はこのCSVには出力しません。
Eval接続契約をJRAの開催日・場・Rへ固定するためです。

## 5. コード変換

CSVには**原コードを保存**します。
表示名が必要な側で以下の対応表を使います。

### `venue_code`

```text
01 札幌
02 函館
03 福島
04 新潟
05 東京
06 中山
07 中京
08 京都
09 阪神
10 小倉
```

### `race_type_code`

```text
11 2歳
12 3歳
13 3歳以上
14 4歳以上
20 障害
99 その他
```

### `race_symbol_code`

3桁コード。

1桁目: 馬の種類条件

```text
0 なし
1 ○混
2 ○父
3 ○市○抽
4 九州産限定
5 ○国際混
```

2桁目: 性別条件

```text
0 なし
1 牡馬限定
2 牝馬限定
3 牡・せん馬限定
4 牡・牝馬限定
```

3桁目: 交流競走指定

```text
0 なし
1 ○指
2 □指
3 ○特指
4 若手
```

したがって牝馬限定判定は、

```python
is_filly_only = race_symbol_code[1:2] == "2"
```

で行えます。

### `weight_condition_code`

```text
1 ハンデ
2 別定
3 馬齢
4 定量
```

### `turn_direction_code`

```text
1 右
2 左
3 直
9 他
```

### `inner_outer_code`

```text
1 通常（内）
2 外
3 直ダ
9 他
```

障害ではJRDB仕様上、トラック情報3桁の組合せに特別な意味があります。

```text
393 障害直線ダート
391 障害直線芝
```

このツールは3項目を分けた生コードとして保持します。

### `course_code`

```text
1 A
2 A1
3 A2
4 B
5 C
6 D
```

### `event_region_code`

```text
1 関東
2 関西
3 ローカル
```

## 6. 対応するRaw配置

入力パス配下を再帰探索します。

認識するファイル名:

```text
BAC_2025.zip
BAC260823.zip
BAC250824.txt
```

したがって、Rawの実際のフォルダ構成を固定しません。

例:

```text
raw/
  BAC/
    BAC_2024.zip
    BAC_2025.zip
    2026/
      BAC260822.zip
      BAC260823.zip
```

でも、

```text
raw/
  archive/
    BAC_2025.zip
  daily/
    BAC260823.zip
```

でも利用できます。

## 7. 期間指定

```bash
python export_jrdb_eval_race_conditions.py \
  --raw /path/to/jrdb/raw \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --output eval_race_conditions_2025.csv
```

開始日・終了日は両端を含みます。

片方だけでも指定できます。

## 8. 対象レース一覧指定

入力CSV:

```csv
race_date,venue_code,race_no
2025-08-24,04,11
2025-08-24,01,11
2025-08-24,07,11
```

実行:

```bash
python export_jrdb_eval_race_conditions.py \
  --raw /path/to/jrdb/raw \
  --targets-csv eval_targets.csv \
  --fail-on-missing-target \
  --output eval_race_conditions_selected.csv
```

`venue_code` は `4` と書いても `04` に正規化します。

`race_date` は以下を許可します。

```text
2025-08-24
20250824
```

### 期間 + 対象一覧

両方指定した場合はAND条件です。

## 9. 重複と訂正データ

同じ

```text
race_date + venue_code + race_no
```

が複数入力ソースから見つかった場合:

- 12出力項目が完全一致 → 同一重複としてcollapse
- 値が異なる → **推測で新版を選ばずエラー終了**

JRDB Rawでは延期・代替開催・訂正等により、同一キーの差分を慎重に扱う必要があるためです。

競合が発生した場合は、Core Builder側と同様に他TYPEとの整合や訂正履歴を確認してから解決してください。

## 10. BACデータ区分について

BACには `データ区分` があり、

```text
1 特別登録
2 想定確定
3 前日
```

です。

このツールの出力12列には含めていません。

Raw年次ZIPや確定済み履歴を前提に使う場合は通常問題ありませんが、開催前の複数段階BACを同時に入力する運用へ拡張する場合は、`データ区分` を監査列として追加することを推奨します。

## 11. Excel / Eval台帳との結合

Eval台帳側で開催場名を持っている場合、先に場コードへ変換します。

```text
新潟 -> 04
札幌 -> 01
中京 -> 07
```

その後、

```text
Eval:
  開催日 + venue_code + R

補助CSV:
  race_date + venue_code + race_no
```

で結合します。

## 12. 依存関係

Python標準ライブラリのみ。

```text
argparse
csv
datetime
pathlib
re
zipfile
```

追加pip install不要です。

## 13. Analysis Liteとの関係

このモジュールは以下を行いません。

- Analysis Lite schema変更
- Analysis Lite SQLite更新
- Analysis Lite再生成
- Analysis Liteへの列追加

構成:

```text
JRDB Raw BAC
    |
    +--> Analysis Lite（既存用途・変更なし）
    |
    +--> export_jrdb_eval_race_conditions.py
             |
             +--> Eval補助CSV
                       |
                       +--> Eval台帳
```

## 14. 再利用時の最小契約

別プロジェクト側は以下だけ知れば利用できます。

入力:

```text
JRDB Raw BAC
```

出力粒度:

```text
1レース1行
```

結合キー:

```text
race_date + venue_code + race_no
```

出力スキーマ:

```text
race_date TEXT YYYY-MM-DD
venue_code TEXT
race_no INTEGER
race_name TEXT
race_type_code TEXT
race_symbol_code TEXT
weight_condition_code TEXT
declared_field_size INTEGER
turn_direction_code TEXT
inner_outer_code TEXT
course_code TEXT
event_region_code TEXT
```

コード値はJRDB公式コード表を正本とし、CSVでは生コードを保持します。

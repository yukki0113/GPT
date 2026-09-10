# NAR official CSV data notes

## Source

NAR「データダウンロード機能説明書」（2026-05-21更新）を一次仕様とする。

https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf

仕様変更はあり得るため、コード側はヘッダー不一致を黙って通さず停止する。

## Availability

| kind | official coverage | monthly update |
| --- | --- | --- |
| race | 1998-01以降 | 1日1回、午前2時頃 |
| odds | 2026-03以降 | 1日1回、午前2時頃 |

過去レース情報には欠損等が生じている場合があると公式説明書に記載されている。

## Monthly endpoints

Phase 0では以下の月次取得エンドポイントを使用する。

~~~text
https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?type=monthly&k_year=YYYY&k_month=M
https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload?type=monthly&k_year=YYYY&k_month=M
~~~

レスポンスはZIP。Content-Dispositionに公式ファイル名があればそのbasenameを原本名として採用する。

## ZIP contents

### race

~~~text
YYYYMM_racelist.csv
YYYYMM_horselist.csv
YYYYMM_payback.csv
~~~

### odds

~~~text
YYYYMM_01_odds.csv
YYYYMM_02_odds.csv
YYYYMM_03_odds.csv
~~~

オッズは1-10日、11-20日、21日-月末の3分割。

## Official schemas

- racelist: 66列
- horselist: 36列
- payback: 54列
- odds: 10列

列名の正本は `nar/schema/` に定義する。

## 2026-09 observed sample

手動取得した以下の公式ZIPでPhase 0仕様を確認した。

~~~text
202609_1788973251_race.zip
202609_1788973251_odds.zip
~~~

観測結果:

- race ZIP: `202609_racelist.csv` 548行 / `202609_horselist.csv` 5,570行 / `202609_payback.csv` 447行
- odds ZIP: `202609_01_odds.csv` 549,085行、`02` / `03` はヘッダーのみ
- CSVはUTF-8 BOM付き
- 公式列数 66 / 36 / 54 / 10 と一致

この観測値は恒久仕様ではなく、2026-09-10時点のサンプル検証値として扱う。

## Pre-race / post-race caution

`horselist` は出馬表情報と結果情報を同じ行に持つ。
着順、タイム、着差、上がり3F等は結果後情報として扱う。

`人気` は結果確定前の月次ファイルで不安定な値を観測したため、pre-race特徴量として使用しない。

`騎手成績`、`全成績`、左右成績、当競馬場成績、当距離成績等は2026-09サンプルでは次走時に前走結果分だけ更新される挙動を確認した。ただし、本格的なモデル利用前に期間を広げてas-of時点性を再検証する。

## Exceptional races

- paybackは同着時に同一レースが複数行となる場合がある。
- 中止・不成立・返還では「レースあり / 結果なし / オッズなし / 返還払戻」の組み合わせがあり得る。
- 単純な欠損補完で通常レースに混ぜない。

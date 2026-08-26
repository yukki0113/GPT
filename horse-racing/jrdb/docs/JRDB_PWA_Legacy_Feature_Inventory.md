# JRDB PWA Legacy Feature Inventory / 再構成方針

## 1. 目的

旧 JRA-VAN 版「検証ラボ」の Git 正本を棚卸しし、JRDB 版へ引き継ぐ機能、別系統へ分離する機能、現在の Stats Mart では不足する機能を整理する。

あわせて、JRDB Analysis Lite v1.2 実データを用いて追加 Mart 候補と PWA 専用 row-level Fact Lite の規模・速度を実測し、今後の PWA データ構成を判断する。

---

## 2. 旧 Git 正本に実在する PWA 機能

対象:

- `horse-racing/legacy/kenshow_labo_jravan/docs/index.html`
- `horse-racing/legacy/kenshow_labo_jravan/docs/app.js`
- `horse-racing/legacy/kenshow_labo_jravan/readme.md`

### 2.1 SQLite 手動読込

旧版は `<input type="file">` から SQLite を選択し、sql.js でメモリロードする。

JRDB 版ではこの役割はすでに次へ置換済み。

```text
旧: 手動ファイル選択
新: remote manifest -> 自動同期 -> OPFS current.sqlite
```

手動取込は非常時・復旧用途だけ残す。

### 2.2 DB 件数確認

旧版は以下のテーブル件数をデバッグ確認できた。

- `dim_race`
- `fact_race_result`
- `fact_payout`
- `fact_race_entry`
- `fact_race_expectation`
- `dim_horse_pedigree`
- `has_entry=1` race count

JRDB 版では通常 UI には不要だが、`DB情報 / 診断` の折りたたみ領域へ次を残す価値がある。

- DB version
- schema version
- period
- row counts
- SHA-256
- integrity status
- last sync

### 2.3 過去レース検索

旧版の検索条件:

- 期間 From / To
- 場コード
- 芝 / ダ
- 距離
- WIN5 only

検索結果:

- 日付
- 場
- R
- レース名
- 芝ダ
- 距離
- クラス
- WIN5

JRDB Analysis Lite v1.2 には日付 / 場 / R / 芝ダ / 距離 / race condition / grade はあるが、`race_name` と `WIN5` は含まれない。

したがって、この旧機能をそのまま復活させる場合は BAC 由来の race-level auxiliary data が必要になる。

現行 PWA の主目的は条件集計なので、MVP では復活対象外とし、必要になった時点で Race Browser として別画面化する。

### 2.4 過去レース詳細

旧版は race detail で次を表示した。

- 着順
- 枠
- 馬番
- 馬名
- 時計
- オッズ
- 人気
- 払戻

Analysis Lite には horse-level の `finish`, `final_win_odds`, `final_win_popularity`, `win_payout`, `place_payout` はある。

一方、旧 `fact_payout` のような全券種・組番払戻は Analysis Lite にはない。

よって、JRDB 版で簡易結果画面は作れるが、旧版と同等の払戻詳細を復活させるには別データが必要。

### 2.5 今週の指数つき出馬表 / 新聞

旧版には `has_entry=1` の週末レース一覧と `vw_newspaper_rows` があり、次を表示した。

- 枠 / 馬番 / 馬名
- 騎手
- 斤量
- expected_100
- ability
- course/style/frame/blood/jockey multipliers
- sire / dam / siresire

この機能は現在の JRDB プロジェクトでは RaceNote 系の責務と重なる。

PWA 条件集計画面へ混ぜず、RaceNote / race-specific view として分離する。

---

## 3. Git に残っていない旧構想

過去の設計では条件集計 UI として、騎手・種牡馬・脚質・枠・年齢・性別・人気・斤量・馬体重・前走条件等をタブで切り替える構想があった。

ただし、2026-08-26 時点の `horse-racing/legacy/kenshow_labo_jravan/docs/` Git 正本には、その条件集計版 HTML / JS は存在しない。

したがって今後は、記憶上の旧 UI を復元するのではなく、JRDB 現行データから要件を再定義する。

---

## 4. 現行 JRDB Stats Mart v1.1

現行共通条件:

- year
- venue_code
- track_type
- distance
- track_condition_code

現行集計軸:

- sire
- jockey
- frame

現行 measures:

- starts
- wins
- seconds
- thirds
- top3
- win_payout_sum
- place_payout_sum

2016-2026 YTD through 2026-08-23:

- sire: 208,885 rows
- jockey: 165,739 rows
- frame: 40,634 rows
- SQLite: 56,254,464 bytes / 約53.65 MiB

この構成は実機 iOS Chrome で OPFS 保存・復元・自動同期・完全オフライン集計まで成立済み。

---

## 5. Analysis Lite から追加 Mart を作った場合の実測

Analysis Lite v1.2:

- 513,512 entries
- SQLite: 197,492,736 bytes
- `PRAGMA integrity_check = ok`

現行 Mart と同じ共通粒度

```text
year
venue_code
track_type
distance
track_condition_code
+ 集計軸
```

で候補 Mart を試作した。

| 軸 | yearly rows | table+index approx |
|---|---:|---:|
| running_style | 21,854 | 1.21 MiB |
| broodmare_sire | 262,052 | 24.89 MiB |
| sire_line | 45,928 | 2.74 MiB |
| broodmare_sire_line | 73,502 | 4.38 MiB |
| popularity exact | 76,999 | 4.21 MiB |
| popularity band | 25,213 | 1.47 MiB |
| training_index band | 26,564 | 1.61 MiB |
| distance_aptitude | 18,922 | 1.05 MiB |
| uptrend | 10,849 | 0.61 MiB |
| race_condition | 13,303 | 0.79 MiB |
| grade | 8,802 | 0.52 MiB |
| age | 24,430 | 1.34 MiB |
| sex | 14,227 | 0.80 MiB |

全候補を追加した試作 DB は約45.6 MiB。

現行 Mart 53.6 MiBへ単純追加すると全体は約100 MiB級になる。

特に `broodmare_sire` 単独で約24.9 MiBを占める。

---

## 6. 軸別 Mart 方式の制約

軸別 Mart は「その軸を GROUP BY する」用途には非常に速い。

ただし、例えば

```text
東京
芝1600
3歳
牡馬
1-3番人気
脚質=先行
```

の条件で「種牡馬ランキング」を出したい場合、`age / sex / popularity / running_style` を `mart_sire_yearly` の grain にも持たせる必要がある。

つまり、集計軸を増やすだけなら安価だが、**自由な cross-filter を増やすと各 Mart の粒度が爆発する**。

今回の「検証ラボ」の主目的は自由条件検証なので、ここが重要な制約になる。

---

## 7. PWA 専用 Fact Lite 試作

Analysis Lite から、集計に不要な馬名・race key 等を落とし、種牡馬 / 母父 / 騎手の名称を dictionary ID 化した row-level SQLite を試作した。

### 7.1 Fact fields

試作では 1出走1行で次を保持。

- race_date_int
- year
- venue_code
- race_no
- track_type
- distance
- race_condition_code
- track_condition_code
- grade_code
- frame_no
- sex_code
- age
- sire_id
- bms_id
- sire_line_code
- bms_line_code
- jockey_id
- running_style
- distance_aptitude
- uptrend
- training_index
- final_win_popularity
- finish
- win_payout
- place_payout

Dictionary:

- dim_sire
- dim_bms
- dim_jockey

### 7.2 Size

513,512 rows を保持し、index を

- course: `(year, venue_code, track_type, distance, track_condition_code)`
- date: `race_date_int`

だけに絞った試作は **約47.4 MiB**。

現在の Stats Mart 53.6 MiB より小さい。

### 7.3 Desktop SQLite timing reference

同一マシン上の参考計測:

| Query | median |
|---|---:|
| 2017-2026 全体 sire ranking | 約429 ms |
| 2017-2026 全体 broodmare sire ranking | 約380 ms |
| 東京芝1600良 sire ranking | 約35 ms |
| 東京芝1600 + 人気1-3 + 牡 + 3歳 sire ranking | 約37 ms |

これはスマホ実機値ではないため、採用判定には iPhone PoC が必要。

ただし、容量と desktop query speed の両方から、Fact Lite を試す価値は高い。

---

## 8. 再構成案

### 8.1 推奨

次の構成を優先評価する。

```text
JRDB Analysis Lite
    |
    +-> PWA Fact Lite  約47 MiB
    |      1出走1行
    |      自由 WHERE / GROUP BY
    |
    +-> Stats Mart
           超頻出 / 全期間ランキングの acceleration cache
```

つまり Stats Mart を捨てるのではなく、役割を

- Fact Lite = flexible exploration
- Stats Mart = acceleration

へ明確化する。

### 8.2 期待する利点

Fact Lite が実機で十分速ければ、次の条件を cross-filter として自由に組み合わせられる。

- year / date
- venue
- track type
- distance
- track condition
- race condition
- grade
- frame
- age
- sex
- sire
- broodmare sire
- sire line
- broodmare sire line
- jockey
- running style
- distance aptitude
- uptrend
- training index / band
- final popularity / band

集計軸も同じ項目群から自由に選べる。

この方が旧構想の「タブを切り替えて条件検証」に近い。

---

## 9. 旧機能の JRDB 版での扱い

| 旧機能 | JRDB版 |
|---|---|
| SQLite手動読込 | 自動同期 + OPFSへ置換済み |
| 件数確認 | DB情報/診断へ縮小して継承 |
| 過去レース検索 | MVP外。必要ならBAC auxiliary追加 |
| 結果詳細 | Analysisベースで簡易版可能。MVP外 |
| 全券種払戻 | Analysisだけでは不足。別データ必要 |
| 週末新聞 | RaceNote系へ分離 |
| 条件集計 | 現行PWAの本丸として再構築 |

---

## 10. 次の実装順

1. `build_jrdb_pwa_fact_lite.py` を正式PoCモジュール化
2. schema / README を追加
3. 現行 Analysis v1.2 から Fact Liteを再生成
4. Stats Martとは別artifactとして配布
5. PWAにデータソース切替PoCを追加
6. iOS Chromeで約47 MiB Fact Liteを実機ロード
7. 次を実測
   - 起動/同期時間
   - OPFS復元
   - 10年全体 sire ranking
   - broodmare sire ranking
   - course-specific query
   - 3-5条件 cross-filter query
8. 実機で許容できれば Fact Liteを条件集計の主データへ昇格
9. 遅い集計だけ Stats Martへ逃がす

---

## 11. 判定基準

Fact Lite PoC は次を目安にする。

- SQLite: 100 MiB未満
- 初回同期: 現行Martと同程度の実用範囲
- OPFS復元: 数秒以内
- course-specific aggregation: 体感待ちなし
- broad 10-year aggregation: 1-2秒程度までなら許容候補
- offline operation: current PWAと同様に成立

このPoCを通すまでは、追加 Mart を大量に恒久追加しない。

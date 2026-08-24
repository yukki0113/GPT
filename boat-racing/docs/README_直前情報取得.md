# BOAT RACE直前情報取得スクリプト

`fetch_boatrace_pre_race_info.py` は、BOAT RACE公式サイトの **出走表** と **直前情報** を同時に取得し、直前予想に渡せるJSONまたはCSVを作成します。公式の `racelist` と `beforeinfo` 以外へはアクセスせず、結果・払戻・オッズは取得しません。

## セットアップ

```bash
pip install requests beautifulsoup4
```

## 実行例

```bash
python fetch_boatrace_pre_race_info.py --date 2026-08-06 --venue 三国 --race 1 --format json
python fetch_boatrace_pre_race_info.py --date 20260806 --venue 10 --race 1 --format csv --output 20260806_直前情報_三国_1R.csv
```

会場は名称または公式会場コードで指定できます。出力JSONはレース単位、CSVは艇ごとに1行です。

## 取得対象

- 日付・会場・R・取得日時
- 出走表の選手情報（枠、登録番号、選手名、級別、支部、出身地、年齢、体重、F/L数、平均ST）
- 全国・当地の勝率／2連率／3連率、モーター・ボートの番号／2連率／3連率
- 今節成績（`current_meet_results`。日・レース番号・進入コース・ST・成績を1走ずつ保持）
- コース別成績（公式出走表ページにない場合は、補完せず `NOT_AVAILABLE`）
- レース全体情報（レース名、レース種別、締切予定時刻、開催日目、最終日フラグ、距離）
- 展示タイム
- 展示進入・スタート展示ST
- 気温・水温・天候・風向・風速・波高

`start_exhibition` は必ず `exhibition_course`、`boat_number`、`start_exhibition_st` の3項目を持ちます。展示コースと艇番は別の値として扱うため、枠なりでない進入でも対応を保持できます。

## JSON／CSV構造

JSONはレース単位です。`racecard_racers` に6艇を格納し、`race_info` にレース全体情報、`weather.start_exhibition` に展示進入を格納します。

CSVは1艇1行で、列名と列数は常に固定です。`current_meet_results`、`course_performance`、`start_exhibition`、`field_states` などの配列・オブジェクトはJSON文字列として格納します。

今節成績の対応が公式HTMLで確認できる場合は、次の形式です。

```json
{"day": 1, "race": 6, "course": 4, "finish": "3", "st": ".09"}
```

公式ページの構造変更などで4行（レース番号／進入／ST／成績）の対応を確認できない場合は、推測して結合せず、`current_meet_race_numbers`、`current_meet_courses`、`current_meet_start_times`、`current_meet_finishes` を別配列で出力します。欠場・転覆・失格・妨害・F・L等の公式文字列も `finish` に文字列のまま保持します。

## 成功／失敗の見方

`fetch_status` が `success` の場合だけ、出走表6艇分と必須の直前情報が揃っています。直前情報がまだ公開されていない、または必須項目が空欄なら `failed` になります。

`failure_kind` の意味は以下です。

| 値 | 意味 |
|---|---|
| `PAGE_FETCH_FAILED` | 通信、HTTPエラー等でページそのものを取得できなかった |
| `PAGE_PARSED_BUT_REQUIRED_DATA_MISSING` | ページは取得できたが、直前情報未公開・公式ページ構造変更・必須項目欠損などで確定データにできなかった |

JSONの `field_states` では、ページ上の値の状態を別途確認できます。

| state | 意味 |
|---|---|
| `PRESENT` | ページ上に値があり、取得できた |
| `BLANK_ON_PAGE` | ページの対象欄は確認できたが、値自体が空欄だった |
| `MISSING_IN_PAGE` | ページ上で対象欄を検出できなかった |
| `NOT_AVAILABLE` | 公式の対象ページに項目が存在せず、取得対象外として扱った（非公式情報で補完しない） |

`－` または空欄はJSON値を `null` とし、`field_states` で `BLANK_ON_PAGE` と区別します。HTMLに項目が見つからない場合は `MISSING_IN_PAGE`、公式ページの対象外であるコース別成績は `NOT_AVAILABLE` です。`official_row_text` は障害調査・検証用に残しますが、数値はこの文字列の並びから決め打ちで分割しません。

成功判定に必要なのは、出走表6艇・展示タイム6艇・展示進入/ST6艇・気温・水温・天候・風向・風速・波高です。選手の任意成績、コース別成績、レース種別などが空欄または未掲載でも、必須項目が揃っていれば `fetch_status: success` です。公式ページ改修時には任意項目だけが欠落する可能性があるため、`field_states` を確認してください。

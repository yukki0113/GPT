# RaceNote -> JRDB Newspaper Output Contract v0.1

Status: **ACTIVE / INITIAL CONTRACT**

## 1. Purpose

RaceNote predictionの成果物をJRDB Newspaperへ安全にmergeするための、1日単位CSV handoff契約を定義する。

この契約はRaceNote本体bundleやReader ViewをNewspaper Base/historyへ流用するものではない。Newspaperへ渡すのは予想成果物だけとする。

```text
RaceNote prediction
  -> PWA handoff CSV v0.1
     -> Newspaper external merger
        -> horses[].addons.racenote_prediction
        -> race_notes.racenote_short_comment
```

## 2. File unit

- 1日1CSV
- UTF-8 / UTF-8 BOMのどちらも許容
- 1出走馬1行
- 対象日の全レース・全出走馬を含む
- 無印馬も省略しない

推奨ファイル名:

```text
RaceNote_prediction_YYYYMMDD_PWA_handoff_v0_1.csv
```

## 3. Required columns

順序は推奨順。consumerは列名で読む。

```text
date
venue_code
venue
race_no
race_key
horse_no
horse_name
mark
prediction_rank
confidence
race_short_comment
model_version
source_semantic_sha256
```

### Column semantics

| column | contract |
|---|---|
| `date` | `YYYY-MM-DD`。CSV内は1日だけ |
| `venue_code` | JRDB 2桁文字列。例 `01`, `09`。数値化して先頭0を失わない |
| `venue` | 人間監査用の開催場名。Newspaper raceと完全一致 |
| `race_no` | 1..12 |
| `race_key` | JRDB race identity。Newspaper raceと完全一致 |
| `horse_no` | 馬番。1以上 |
| `horse_name` | 誤結合防止用。Newspaper horse nameと完全一致 |
| `mark` | `◎ / ○ / ▲ / △ / 空欄` |
| `prediction_rank` | レース内の全出走馬に1..Nを付与。重複・欠番不可 |
| `confidence` | `A / B / C`。同一レース内で同値 |
| `race_short_comment` | レース全体の短評・展開見立て。同一レース内で同値 |
| `model_version` | RaceNote prediction model/logic version。同一レース内で同値 |
| `source_semantic_sha256` | そのレースのRaceNote prediction入力を追跡する64桁SHA-256。同一レース内で同値 |

## 4. Mark / rank contract

v0.1では印を次へ固定する。

```text
rank 1 -> ◎
rank 2 -> ○
rank 3 -> ▲
rank 4 -> △
rank 5 -> △
rank 6以降 -> 空欄
```

`prediction_rank` は印対象馬だけでなく全馬へ付ける。

これによりNewspaperは通常表示では印だけを使い、将来の上位N頭表示・比較等ではrankを再生成せず利用できる。

## 5. Merge key and validation

主join key:

```text
date + venue_code + race_no + horse_no
```

さらに次をcross-checkする。

```text
race_key
venue
horse_name
```

馬名の近似一致、表記ゆれ補正、race_key推測によるmergeは禁止する。

RaceNote CSVはcomplete sourceとして扱うため、対象Newspaper dayに対して次をすべて満たす必要がある。

- race count complete
- horse count complete
- duplicate key = 0
- missing row = 0
- extra row = 0
- horse_name mismatch = 0
- race_key mismatch = 0
- venue mismatch = 0
- rankが各レースで `1..N` の完全順列
- mark/rank contract一致
- `confidence / race_short_comment / model_version / source_semantic_sha256` が同一レース内で一意

不一致時はfail-closedとし、自動補正しない。

## 6. Newspaper projection

馬単位の成果物は次へmergeする。

```json
{
  "addons": {
    "racenote_prediction": {
      "mark": "◎",
      "prediction_rank": 1,
      "confidence": "B",
      "model_version": "<model_version>",
      "source_semantic_sha256": "<64 hex>",
      "source": "RaceNote prediction",
      "source_date": "YYYY-MM-DD"
    }
  }
}
```

レース単位短評は各馬へ重複保持せず、次へ1回だけ投影する。

```json
{
  "race_notes": {
    "racenote_short_comment": "<race_short_comment>"
  }
}
```

Newspaper mergerが所有してよいnamespaceは以下だけ。

```text
horses[].addons.racenote_prediction
race_notes.racenote_short_comment
metadata.source_status.racenote_prediction
manifest.source_status.racenote_prediction
```

JRDB Base/history、Eval、keibailuka、Edge、MyIndexを変更しない。

## 7. Source status

各race bundleでは `metadata.source_status.racenote_prediction` を `READY` にし、最低限次を保持する。

- `source_version`: model_version
- `generated_at`
- `semantic_sha256`: race-level `source_semantic_sha256`
- expected/resolved/unresolved counts
- handoff filenameをmessage等で追跡可能にする

Daily manifestではRaceNote handoff全体のrace/horse merge件数とmodel versionを記録する。

## 8. v0.1 real-data acceptance sample

Initial sample:

```text
RaceNote_prediction_20260905_PWA_handoff_v0_1.csv
```

Expected acceptance target:

- date: 2026-09-05
- races: 36
- horses: 455
- Newspaper exact-key merge: 455/455
- horse/race identity mismatch: 0

このファイル自体は日次生成物でありGit正本へcommitしない。契約・merger・testだけをGitで管理する。

## 9. Change policy

列追加は後方互換を優先する。既存列の意味変更、mark/rank rule変更、join key変更はv0.1を上書きせず新versionとして定義する。

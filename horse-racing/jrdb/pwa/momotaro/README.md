# 桃太郎新聞 PWA

予想の提出・整形・表示運用の正本は [OPERATIONS.md](./OPERATIONS.md) とする。

Kenshow_Labo PWAと同じGitHub Pages artifact内に配置する、独立した公開surfaceです。

## 公開境界

- URL / manifest / Service Worker / shell cacheは `momotaro/` scopeで独立
- Newspaper OPFS: `momotaro-newspaper`
- Fact Lite OPFS: `momotaro-fact-lite`
- Kenshow_Labo固有の画面導線を桃太郎側へ出さない
- 共通利用するのは検証済みのNewspaper配布データ、Fact Lite配布データ、表示runtime
- 桃太郎固有情報は `horse.addons.momotaro` のみで表現し、既存addonを上書きしない

## 桃太郎 addon contract

```json
{
  "addons": {
    "momotaro": {
      "ryota": {
        "mark": "◎",
        "confidence": "S",
        "comment": "短評"
      },
      "oji": {
        "mark": "○",
        "review_horse": true,
        "comment": "回顧・短評"
      },
      "kenshow": {
        "mark": "▲",
        "comment": "短評"
      }
    }
  }
}
```

欠損時は推測せず空表示とする。

## Surfaces

- `newspaper.html`: 既存Newspaper runtimeを共有、過去走5走固定、共有compact historyを使用、桃太郎3人欄を追加
- `predictions.html`: りょーたS / おーじ回顧馬 / イルカの一覧
- `fact-lite.html`: 既存Fact Lite runtimeと配布SQLiteを共有、OPFSだけ桃太郎専用


## イルカ列

🐬は3人の予想とは別の共通外部参考情報として扱う。

- source: `addons.keibailuka`
- 桃太郎3人の `addons.momotaro` へコピーしない
- 新聞では `りょーた / おーじ / けんしょー / 🐬` の4列で表示する
- 🐬の表示・短評dialogはKenshow_Labo個人PWAと同じ既存consumer semanticsを再利用する


## 公開データ投影

桃太郎新聞はKenshow_Labo用Newspaper JSONをブラウザから直接参照しない。

Pages構築時に build_momotaro_newspaper_projection.py で専用projectionを生成し、
momotaro/data/newspaper/current/ から読む。

公開projectionのallowlist:

- JRDB/base新聞情報
- 過去走
- addons.keibailuka
- addons.momotaro

明示的に除外:

- addons.eval
- addons.racenote_prediction
- addons.my_index
- edge_matches
- 元Newspaper auditの詳細

したがって、桃太郎PWAへ個人用addonを表示しないだけでなく、桃太郎側が取得する新聞JSON自体にも個人用addonを含めない。


## 3人予想CSV

日次の3人予想は疎なCSVとして扱う。全馬を埋める必要はない。

current配布チャネル:

- Release tag: jrdb-momotaro-predictions-current
- asset: momotaro_predictions.csv

必須列:

```text
date,venue_code,race_no,horse_no,horse_name,member,mark,confidence,review_horse,comment
```

memberは次の3人だけを許可する。

- ryota / りょーた
- oji / おーじ
- kenshow / けんしょー

exact joinは date + venue_code + race_no + horse_no + member で行い、
horse_nameも一致を必須とする。重複・別日・未消費行はfail-closed。

用途の詳細は OPERATIONS.md を正本とする。

- りょーた: 各Rの通常印は新聞列へ表示。特注馬は review_horse=true + comment としてリンク化し、予想一覧にも掲載する。
- おーじ: 回顧該当馬のみ review_horse=true + comment として、🐬と同様に新聞リンク + 予想一覧へ掲載する。
- けんしょー: RaceNote完成まで保留。JRDB印転記は暫定案であり正式運用ではない。


## 表示方針

新聞:
- 過去走は共有 `newspaper-v4` compact rendererを使用し、5走固定とする。
- history幅は個人PWAと同じ共有値を基準とし、桃太郎固有の固定幅コピーを持たない。
- 運用用の取得状態、source status、手動取込UIは桃太郎側では非表示。
- 印見出しはスマホ幅を優先し、りょ / 王子 / けん / 🐬 とする。
- 自動取得処理自体は維持し、利用者に運用UIを見せない。

予想一覧:
- レース単位で1カードにまとめる。
- 同一レースに複数sourceがある場合はsourceごとに縦積みする。
- 🐬は source label を 🐬 とし、馬番 + 馬名 + コメントを表示する。
- りょーた confidence=S は「次走注目S」と表示する。
- 王子 review_horse=true は「回顧馬」と表示する。


印列幅:
- りょ / 王子 / けん: 32px
- 🐬: 34px


過去走は5走固定。

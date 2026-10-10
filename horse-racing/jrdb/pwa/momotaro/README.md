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
- `predictions.html`: りょーた / 王子 / けんしょー / 🐬 の注目馬一覧。けんしょーはRaceNote/RRDB由来を掲載する。
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

- りょーた: 通常印は新聞列に表示し、レース自信度だけではリンク化・注目馬一覧への掲載をしない。馬単位の短評・回顧コメントがある馬だけ印をリンク化し一覧に掲載する。レース単位【見解】は別のレース短評欄に表示する。
- おーじ: 回顧該当馬のみ review_horse=true + comment として、🐬と同様に新聞リンク + 予想一覧へ掲載する。
- けんしょー: RaceNote/RRDBを正本とする。RaceNoteの印をけん印、RaceNote単馬短評は新聞モーダル専用、RRDB推薦コメントをけんしょー注目馬コメントとして扱う。注目馬一覧にはRRDB該当馬だけを掲載する。RaceNoteレース短評はけんしょーのレース短評として扱う。


## けんしょー = RaceNote / RRDB 運用

けんしょーはKenshow_Labo利用者本人であり、今後はRaceNote/RRDBをけんしょー提出の正本とする。

自動変換:

- `addons.racenote_prediction.mark` → `addons.momotaro.kenshow.mark`
- `addons.racenote_prediction.confidence` → `addons.momotaro.kenshow.confidence`
- `addons.racenote_prediction.horse_short_comment` → 新聞のけん印モーダル専用コメント。注目馬一覧には使用しない
- `addons.rrdb_recommendation.comment` → けんしょー注目馬コメント
- RRDB該当馬 → `review_horse=true`
- `race_notes.racenote_short_comment` → `race_notes.momotaro_comments.kenshow`

RRDB該当馬ではモーダル本文をRRDBコメントとし、RaceNote単馬短評は表示に混在させない。RRDB由来の表示タグは「不利分析」、RaceNote単独表示にはタグを付けない。
明示的な `momotaro.kenshow` 手動入力がある場合は自動値より手動値を優先する。
`tag=手動無印` は印を明示的に空にする。

JRDB総合印をけんしょー印として代用する旧暫定仕様は廃止する。

反映surface:

- 桃太郎新聞の「けん」列・短評
- 桃太郎新聞の注目馬一覧
- 個人PWA新聞の「けん」列・桃太郎短評
- 個人PWAの注目馬一覧

## 表示方針

新聞:
- 新聞ページには「3人の予想・短評」カードを置かない。友人コメントは印セルのモーダル、横断確認は予想一覧を正本とする。
- 過去走は共有 `newspaper-v4` compact rendererを使用し、5走固定とする。
- history幅は個人PWAと同じ共有値を基準とし、桃太郎固有の固定幅コピーを持たない。
- 運用用の取得状態、source status、手動取込UIは桃太郎側では非表示。
- 印見出しはスマホ幅を優先し、りょ / 王子 / けん / 🐬 とする。
- 自動取得処理自体は維持し、利用者に運用UIを見せない。

予想一覧:
- レース単位で1カードにまとめる。
- 同一レースに複数sourceがある場合はsourceごとに縦積みする。
- 🐬は source label を 🐬 とし、馬番 + 馬名 + コメントを表示する。
- りょーたのconfidenceはレース自信度であり、次走注目ランクではない。自信度だけで一覧に掲載しない。
- 王子 review_horse=true は一覧対象判定だけに使い、画面上では「回顧馬」等の区分ラベルを付けず、馬番 + 馬名 + コメントを表示する。


印列幅:
- りょ / 王子 / けん: 24px
- 🐬: 26px


過去走は5走固定。


予想一覧の配布シェル更新時は focused test の asset version / 表示契約も同時に更新し、Pages deploy 成功まで確認する。

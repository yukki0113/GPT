# 桃太郎新聞 PWA

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

- `newspaper.html`: 既存Newspaper runtimeを共有、過去走3走固定、桃太郎3人欄を追加
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

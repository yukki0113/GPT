# Newspaper compact history display

## Status

- Turn 1: completed
- Turn 2: completed
- Turn 3: completed
- Turn 4: completed at practical mobile density limit
- Turn 5: not started

This document is the durable design record for the shared Newspaper past-run compact display.

## Goal

The personal Kenshow_Labo Newspaper and the Momotaro Newspaper share the past-run renderer.

The target is a denser, racing-paper-like history layout so that on a phone, after modest browser zoom-out, roughly four past-run columns can be recognized at once without deleting the underlying JRDB history data.

The change is presentation-only. PACI parsing, Newspaper JSON schema, history generation, and historical data retention are not changed.

## Turn 1 audit

The pre-change v4 history cell used a fixed width of approximately 154-158px and placed most available detailed fields directly inside each cell.

The shared data already contains enough history for the existing personal 3/5/8 selector and the Momotaro fixed-history display. Therefore no upstream data change is required.

Existing detailed-run dialog behavior is retained and expanded so information removed from the dense cell is still available.

## Compact information hierarchy

The compact cell keeps the information needed for quick comparison:

- date
- venue / race number
- grade or class
- race name
- finishing position
- field size / past horse number / popularity when available
- surface / distance / track condition
- race time when available
- corner passage when available
- final 3F when available
- abnormal / trouble flag when available

The following information is primarily moved to the detail dialog:

- jockey
- carried weight
- body weight and change
- time gap
- IDM
- paddock / leg / equipment / race comments
- JRDB detailed metrics

No field is inferred when source data is missing.

## Shared runtime contract

Current implementation:

- shared renderer: `newspaper-v4.js`
- shared layout: `newspaper-v4.css`
- config key: `JRDB_PWA_CONFIG.newspaperHistoryDisplayMode`
- supported modes:
  - `standard`
  - `compact`

If the config is absent or unknown, the renderer uses `standard`.

This fail-safe default prevents a shared runtime update from silently changing another PWA surface.

## Turn 2 activation

Kenshow_Labo personal Newspaper:

```js
window.JRDB_PWA_CONFIG = {
  newspaperHistoryDisplayMode: "compact"
};
```

Momotaro Newspaper:

- Turn 3で shared compact renderer を有効化
- 5走固定を維持
- 桃太郎独自tableにも `newspaperV4HistoryTableClass()` を付与
- 予想4列（りょ / 王子 / けん / 🐬）とcompact historyを同一tableで共存
- history幅はTurn 3では共通値を使用し、実機の微調整はTurn 4へ残す

## Compact sizing

Shared current values:

- desktop/tablet compact history width: 124px
- phone width at max-width 640px: 94px
- phone horse-number width: 28px
- phone horse-name width: 82px
- phone basic-info width: 76px
- compact padding and font metrics are controlled by CSS custom properties

Turn 4 tuning pass 1 used the iPhone screenshot as the reference. The previous 120px phone history width was insufficient for the requested four-column-at-zoom target.

## Detail preservation

Compact mode does not remove source data.

The existing detail dialog is the secondary surface for information omitted from the compact cell, including weight, body weight, time gap, IDM, and detailed JRDB/comment fields.

## Cache isolation

The personal Service Worker must delete only old `jrdb-pwa-shell-*` caches.

It must not delete Momotaro caches or other same-origin cache namespaces.

## Turn 3

桃太郎新聞も `newspaperHistoryDisplayMode: "compact"` を指定し、共有compact rendererへ切り替えた。

桃太郎固有差分は次に限定する。

- 過去走は5走固定
- 予想列は りょ / 王子 / けん / 🐬
- 予想列幅は 32 / 32 / 32 / 34px
- history cell本体は個人PWAと同じ共有renderer / CSSを利用

Turn 3では桃太郎専用のhistory幅上書きは追加しない。共有スマホ幅120pxを基準にし、実機での視認性・4走同時認識の調整はTurn 4で行う。

## Turn 4

iPhone実機スクリーンショットを基準に、mobile compactを再調整した。

変更:

- history: 120px -> 94px
- horse number: 32px -> 28px
- horse name: 103px -> 82px
- basic info: 118px -> 76px
- compact時のbasic infoは父・脚質を省略し、性齢/斤量・騎手を優先
- compact historyのfont / line-height / paddingを一段圧縮
- 桃太郎の予想group headerは共有230pxを継承せず、実際の4列合計に合わせ130pxへ固定

桃太郎の各予想列幅 32 / 32 / 32 / 34px は変更しない。

Turn 4 pass 2では、94px幅を維持したままcompact内のfont size / line-heightを一段下げ、文字の衝突を抑えた。

実機上はこれ以上history幅を削ると可読性とタップ操作の劣化が大きくなるため、94pxを実用上の下限とする。友人共有時の案内も「現行compactがスマホ縦持ちでの実用上の限界」とする。

## Next turn

Turn 5:

- 最終回帰確認
- 個人3/5/8切替、桃太郎5走固定、詳細dialogの回帰確認
- 運用文書の最終確定

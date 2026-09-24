# Newspaper compact history display

## Status

- Turn 1: completed
- Turn 2: completed
- Turn 3: not started
- Turn 4: not started
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

- shared renderer is available
- compact mode is not enabled yet
- activation and Momotaro-specific width balance belong to Turn 3

## Compact sizing

Shared current values:

- desktop/tablet compact history width: 124px
- phone width at max-width 640px: 120px
- compact padding and font metrics are controlled by CSS custom properties

The exact final phone density remains subject to Turn 4 real-device adjustment.

## Detail preservation

Compact mode does not remove source data.

The existing detail dialog is the secondary surface for information omitted from the compact cell, including weight, body weight, time gap, IDM, and detailed JRDB/comment fields.

## Cache isolation

The personal Service Worker must delete only old `jrdb-pwa-shell-*` caches.

It must not delete Momotaro caches or other same-origin cache namespaces.

## Next turn

Turn 3:

- opt Momotaro into the shared compact renderer
- retain Momotaro fixed five-run display
- verify prediction columns and five compact history columns coexist
- adjust Momotaro-specific horizontal balance only where necessary

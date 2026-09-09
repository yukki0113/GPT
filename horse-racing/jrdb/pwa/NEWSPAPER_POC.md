# JRDB Newspaper PWA display PoC

Status: P4 DISPLAY POC

URL after GitHub Pages deployment:

```text
https://yukki0113.github.io/GPT/newspaper.html
```

## Purpose

Validated Newspaper race bundle v0.1をスマホで1頭1行の競馬新聞として表示し、横スクロール・sticky列・3/5/8走切替・オフライン再読込を実機確認する。

P4では日次publisherをまだ前提にせず、監査済み `race.json` を手動取込する。

## Input

Required:

- `schema_version = 0.1`
- `bundle_kind = jrdb_pwa_newspaper_race`
- race identity
- horses array
- history maximum 8
- all history dates strictly before target race date

Real-data reference:

- 2026-08-16 札幌11R 札幌記念
- 16 horses
- 5 detailed + 3 compact per horse
- 128 history rows total
- validated bundle SHA-256 `d18a9cddc077ffec8a651a34863d329b742506c1fd304b74b01aaef93f976e42`

## Display contract

Fixed meaning order:

```text
馬番 -> 馬情報 -> JRDB -> 過去走 -> Edge
```

- 馬番と馬情報をsticky表示
- default 3走
- 5走 / 8走へ切替可能
- detailed 1-5は時計・上がり・IDM・ZKB/JRDB詳細を保持
- compact 6-8はsourceに存在する項目だけ表示し `簡易` labelを付ける
- compactでrace_nameがない場合はgrade/classへfallback
- 競走中止等は着順0/nullを通常着順として表示せず、abnormal codeと詳細コメントを確認可能にする
- Edge未merge時は空欄扱い

## Offline PoC

Imported race JSON is stored to OPFS:

```text
jrdb-newspaper/current.json
```

On later page boot:

1. OPFS availability check
2. `current.json` restore
3. bundle validation
4. render

This allows airplane-mode/offline re-open testing before the production day-manifest publisher exists.

Service Worker shell cache version for initial Newspaper page is `jrdb-pwa-shell-v19`.

## Real-device acceptance

On iPhone/Chrome:

1. open `newspaper.html` online
2. import validated 札幌記念 `race.json`
3. confirm 16 rows
4. confirm horse no + horse info remain visible while horizontal scrolling
5. confirm 3/5/8 toggle
6. confirm アドマイヤテラ Japan Cup displays race discontinuation rather than a fabricated finish
7. open one detailed run dialog and verify comments
8. close/reopen page and confirm OPFS auto-restore
9. switch airplane mode and reopen
10. confirm 3/5/8 display remains usable offline

## Deferred

- daily manifest sync
- Drive canonical save
- Pages data publication
- addon merge
- Edge merge
- automatic current-day prefetch

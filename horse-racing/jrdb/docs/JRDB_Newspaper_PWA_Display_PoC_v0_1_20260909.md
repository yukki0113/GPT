# JRDB Newspaper PWA Display PoC v0.1 — 2026-09-09

Status: IMPLEMENTED / REAL-DEVICE VALIDATION PENDING

## Purpose

`jrdb_pwa_newspaper_race` v0.1 の1レースJSONを、スマホ中心の「自分用競馬新聞」として表示し、OPFS保存・オフライン再表示まで確認するためのPWA表示PoC。

データ生成は `jrdb_newspaper_build.py` が担当し、表示側はRaceNote内部実装へ依存しない。

## Validation data

2026-08-16 札幌11R 札幌記念。

- 16頭
- detailed history: 5走 × 16頭 = 80走
- compact older history: 3走 × 16頭 = 48走
- total history: 128走
- race JSON pretty size: 307,691 bytes
- chronology violation: 0
- duplicate history identity: 0
- schema validation: PASS
- forbidden `racenote_*` import: 0

アドマイヤテラの2025-11-30ジャパンCは `abnormal_code=3` かつZKBコメントが落馬・競走中止を示し、上がり/IDM等の欠損は正常な競走中止データとして扱う。

## PWA files

- `pwa/newspaper.html`
- `pwa/newspaper.js` — v1 base storage/validation/render foundation
- `pwa/newspaper-v2.js` — display-order/addon/race-note UI patch
- `pwa/newspaper.css`
- `pwa/service-worker.js` — shell v20

## Display order

ユーザー指定の意味順を固定する。

```text
枠 -> 馬番 -> 馬情報 -> 印群 -> 前走 -> 2走前 -> 3走前 ... -> Edge
```

スマホでは枠・馬番・馬情報をsticky固定し、印群以降を横スクロールする。

### 馬情報

現PoCでは以下を表示する。

- 馬名
- 性齢
- 斤量
- 騎手
- 父
- 脚質

### 印群

固定slotを先に用意し、未取得sourceは `—` とする。

- JRDB能力: IDM
- JRDB調教: 調教指数 + 調教矢印
- Eval
- RaceNote prediction
- イルカブログ
- My Index
- JRDB各印（総/能/情/騎/厩/調/穴）

イルカブログaddonに短評が入った場合は `○` を押してdialog表示する。

### 過去走

- 初期表示: 3走
- toggle: 5走 / 8走
- 1-5走: `detailed_recent_history`
- 6-8走: `compact_older_history`、画面上に「簡易」表示
- レース名/grade/class
- 芝ダ + 距離 + 馬場
- 着順/頭数、人気
- コーナー通過順
- detailedのみ時計/上がり/IDM
- abnormal codeを持つ競走中止等は通常着順と分けて表示
- detailedの「詳細」からZKBコメント等をdialog表示

### Edge

`edge_matches[].display_text` を末尾列へ表示する。未merge時は `—`。

### レース短評

出走表の下に専用sectionを持つ。

- `race_notes.racenote_short_comment`
- `race_notes.items[]`

未取得時は空欄ではなく「現時点では未取得」と表示する。

## Offline PoC

手動で1レースJSONを選択し、browser-side validation後にOPFSへ `jrdb-newspaper/current.json` として保存する。

次回起動時はOPFSから復元する。Service Worker shell v20にはNewspaper HTML/JS/CSSも含めるため、shell更新後は機内モードでの起動・復元確認が可能。

日次manifest、自動同期、複数レース保存は後続フェーズ。

## Deployment

PWA Pages run #150 / run id `34309359955`、head `d12637d8a08e62992fc83a757b9b79b1750f7139` は success。

## Real-device acceptance checklist

1. `newspaper.html` をオンラインで一度開く。
2. 札幌記念 `race.json` を取り込める。
3. 16頭が馬番順で表示される。
4. 枠 / 馬番 / 馬情報が横スクロール中も固定される。
5. 意味順が `馬情報 -> 印群 -> 過去走 -> Edge` になっている。
6. 3走 / 5走 / 8走切替が即時反映される。
7. 8走表示時、6-8走に「簡易」が付く。
8. アドマイヤテラのジャパンCが「競走中止」と表示され、詳細に落馬コメントが出る。
9. OPFS保存後、タブ/PWA再起動で自動復元する。
10. shellを一度更新後、機内モードで起動・表示できる。
11. 横幅、文字サイズ、1頭あたり行高がiPhone実用上許容できる。

実機で密度に違和感があれば、データcontractを変えずCSS/初期表示情報だけを調整する。

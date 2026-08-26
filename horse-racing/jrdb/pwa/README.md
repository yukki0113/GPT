# JRDB 検証ラボ PWA

JRDB Stats Mart をスマホ端末へ保存し、競馬場など通信が不安定な場所でも条件集計できるオフライン PWA のフロントエンド正本です。

## Deployment

GitHub Pages は GitHub Actions 方式を使用します。

- source: `horse-racing/jrdb/pwa/`
- workflow: `.github/workflows/jrdb_pwa_pages.yml`
- target branch: `main`
- default Pages URL: `https://yukki0113.github.io/GPT/`

`pwa/**` または Pages workflow が `main` で更新されると自動デプロイします。

## Current phase

Phase 2 PoC では、Stats Mart v1.1 を実機へ一度取り込み、OPFS に永続保存して次回起動時に自動復元する経路を実装しています。

実装済み:

- mobile-first UI
- Web App Manifest
- Service Worker
- app shell の事前キャッシュ
- online / offline 表示
- OPFS 利用可否チェック
- sql.js 1.14.1 + WASM の固定version利用
- sql.js / WASM の Service Worker キャッシュ
- Stats Mart SQLite の手動初回取込
- 必須3テーブル確認 / `PRAGMA integrity_check`
- OPFS `jrdb/current.sqlite` への永続保存
- 次回起動時の OPFS 自動復元
- 種牡馬 / 騎手 / 枠の集計
- 年 / 競馬場 / 芝ダ障害 / 距離 / 馬場状態 / 最低出走数フィルタ
- 勝率 / 複勝率 / 単勝回収率 / 複勝回収率表示

未実装:

- remote manifest による最新版確認
- Google Drive 等からの自動同期 provider
- SHA-256 validation
- current / previous / incoming の安全なDB差し替え
- 追加Mart軸
- sql.js / WASM のGit内vendor化（PoCでは固定CDN版をService Workerへキャッシュ）

## Real-device PoC

初回はオンライン状態で実施します。

1. Pages URL を開く。
2. OPFS が `利用可能`、Service Worker が `登録済み` になることを確認する。
3. `jrdb_stats_mart_2016_2026YTD_20260823_v1_1.sqlite` を選択し `端末へ保存` を押す。
4. `読込済み` になり、種牡馬集計が表示されることを確認する。
5. 競馬場・距離等を変更し、種牡馬 / 騎手 / 枠を切り替えて集計できることを確認する。
6. ページを完全に閉じて開き直し、ファイル選択なしで `OPFSから復元` されることを確認する。
7. 一度オンラインで正常起動した後、機内モード等で再度開き、PWA shell と保存済み Stats Mart だけで集計できることを確認する。

このPoCの目的は、自動同期実装前に約54MiB級Stats Martの端末保存・復元・sql.js集計性能を実機で測ることです。

## Data policy

GitHub Pages には PWA の UI / JS / CSS 等だけを配置します。
JRDB Raw、Analysis Lite、Stats Mart SQLite は Git 管理外とし、最終形では外部ストレージから端末へ自動同期します。

詳細設計は `../docs/JRDB_PWA_Offline_Sync_Design.md` を参照してください。

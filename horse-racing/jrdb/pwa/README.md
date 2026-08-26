# JRDB 検証ラボ PWA

JRDB Stats Mart をスマホ端末へ同期し、競馬場など通信が不安定な場所でも条件集計できるオフライン PWA のフロントエンド正本です。

## Deployment

GitHub Pages は GitHub Actions 方式を使用します。

- source: `horse-racing/jrdb/pwa/`
- workflow: `.github/workflows/jrdb_pwa_pages.yml`
- target branch: `main`
- default Pages URL: `https://yukki0113.github.io/GPT/`

`pwa/**` または Pages workflow が `main` で更新されると自動デプロイします。

## Current phase

Phase 1 の目的は Pages 配信とオフライン shell の成立確認です。

実装済み:

- mobile-first の最小画面
- Web App Manifest
- Service Worker
- app shell の事前キャッシュ
- online / offline 表示
- OPFS 利用可否チェック

未実装:

- sql.js / WASM の同梱
- Stats Mart SQLite の OPFS 保存
- remote manifest による最新版確認
- SHA-256 / integrity_check / schema validation
- current / previous / incoming の安全なDB差し替え
- 種牡馬 / 騎手 / 枠の実集計

## Data policy

GitHub Pages には PWA の UI / JS / CSS / WASM 等だけを配置します。
JRDB Raw、Analysis Lite、Stats Mart SQLite は Git 管理外とし、外部ストレージから端末へ同期します。

詳細設計は `../docs/JRDB_PWA_Offline_Sync_Design.md` を参照してください。

# JRDB 検証ラボ PWA

JRDB Stats Mart をスマホ端末へ保存し、競馬場など通信が不安定な場所でも条件集計できるオフライン PWA のフロントエンド正本です。

## Deployment

GitHub Pages は GitHub Actions 方式を使用します。

- source: `horse-racing/jrdb/pwa/`
- UI workflow: `.github/workflows/jrdb_pwa_pages.yml`
- data publish workflow: `.github/workflows/jrdb_pwa_publish_data.yml`
- target branch: `main`
- default Pages URL: `https://yukki0113.github.io/GPT/`

`pwa/**` または Pages workflow が `main` で更新されると自動デプロイします。

## Current phase

Phase 3 では、実機PoCで成立した OPFS / sql.js 基盤へ remote manifest と安全なStats Mart自動同期を追加しました。

実装済み:

- mobile-first UI
- Web App Manifest
- Service Worker
- app shell の事前キャッシュ
- online / offline 表示
- OPFS 利用可否チェック
- sql.js 1.14.1 + WASM の固定version利用
- sql.js / WASM の同一origin配信・Service Workerキャッシュ
- Stats Mart SQLite の手動復旧取込
- 必須3テーブル確認 / `PRAGMA integrity_check`
- OPFS `jrdb/current.sqlite` への永続保存
- 次回起動時の OPFS 自動復元
- remote `data/manifest.json` による最新版確認
- size / SHA-256 / schema / required tables / integrity validation
- `incoming.sqlite` / `previous.sqlite` / `current.sqlite` による安全な全量差し替え
- GitHub Release を利用したGit非管理の配布キャッシュ
- Google Drive -> Issue -> Actions -> Release -> Pages artifact の配布経路
- 種牡馬 / 騎手 / 枠の集計
- 年 / 競馬場 / 芝ダ障害 / 距離 / 馬場状態 / 最低出走数フィルタ
- 勝率 / 複勝率 / 単勝回収率 / 複勝回収率表示

未実装 / 今後:

- Stats Mart更新生成処理から `[JRDB_PWA_DATA_PUBLISH]` Issue作成までの完全自動連携
- 追加Mart軸
- UIの最終調整

## Real-device validation

2026-08-26 に iOS版Google Chromeで現行 Stats Mart v1.1 を検証しました。

- SQLite size: 約53.6 MiB
- OPFS保存: 成功
- 保存体感: 約1〜2秒
- ページ再起動後のOPFS自動復元: 成功
- 種牡馬 / 騎手 / 枠の集計: 成功
- 条件変更: 成功
- 機内モードでのPWA起動: 成功
- 機内モードでのOPFS復元・集計: 成功

これにより、約54MiB級 Stats Mart を端末常用DBとする基本構成は実機で成立済みです。

## Distribution flow

大容量SQLiteはGitへcommitしません。

```text
Google Drive Stats Mart
  -> [JRDB_PWA_DATA_PUBLISH] Issue
  -> GitHub Actions
  -> size / SHA-256 / SQLite validation
  -> GitHub Release asset (distribution cache)
  -> GitHub Pages artifact /data/
  -> PWA manifest sync
  -> OPFS current.sqlite
```

Google Drive File IDは世代更新で変わり得るためGitへ固定しません。Issue本文だけでその時点のFile IDとartifact metadataを渡します。

通常のPWAコード更新時は `.github/workflows/jrdb_pwa_pages.yml` が `jrdb-stats-mart-current` Releaseの現行assetをPages artifactへ再同梱するため、UI更新で配布DBが消えない構成です。

詳細は `SYNC_PROVIDER.md` を参照してください。

## Local sync behavior

PWA起動時はネットワークより先に OPFS `current.sqlite` を復元します。

オンライン時のみmanifestを確認し、ローカル metadata の SHA-256 と比較します。

- 同一SHA-256: 再ダウンロードしない
- 新版: `data/jrdb_stats_mart.sqlite` を取得
- 取得後: size / SHA-256 / SQLite validation
- validation成功: incoming -> previous/current の順で切替
- validation失敗: current.sqlite を維持

Service Workerは `/data/` をキャッシュしません。オフライン利用は OPFS の current.sqlite を使います。

## Current distribution artifact

2026-08-26 のDrive実ファイルをActionsから再取得して検証した結果:

- source filename: `jrdb_stats_mart_2016_2026YTD_20260823_v1_1.sqlite`
- size: `56,254,464 bytes`
- SHA-256: `1d1798315646996991487c6e0cd5ee40ab330da58a8f77f6950694959a2b9f50`
- required tables: PASS
- `PRAGMA integrity_check`: `ok`
- Release tag: `jrdb-stats-mart-current`

従来READMEに記録されていたSHA-256とは差異があったため、配布workflowではDrive実ファイルを再取得し、実artifactのsize / SHA-256 / SQLite内容を検証した値を採用しています。

## Data policy

JRDB Raw、Analysis Lite、Stats Mart の生成正本は引き続き Git 管理外です。
GitHub Release / GitHub Pages artifact に置く Stats Mart は **PWA配信用キャッシュ** であり、Git正本ではありません。

詳細設計は `../docs/JRDB_PWA_Offline_Sync_Design.md`、実配布方式は `SYNC_PROVIDER.md` を参照してください。

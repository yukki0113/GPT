# JRDB PWA Sync Provider

## Purpose

PWA は Google Drive の個別 File ID を直接保持せず、GitHub Pages 上の固定 manifest から配布版 Stats Mart を同期する。

大容量 SQLite の正本は引き続き Git 管理外ストレージとし、GitHub Release / Pages artifact は PWA 配信用キャッシュとして扱う。

## Publish flow

```text
Google Drive Stats Mart
  -> [JRDB_PWA_DATA_PUBLISH] Issue
  -> GitHub Actions
  -> size / SHA-256 / SQLite integrity validation
  -> GitHub Release asset (distribution cache)
  -> GitHub Pages artifact /data/
  -> PWA manifest sync
  -> OPFS current.sqlite
```

Issue本文にはその時点の Drive File ID と artifact metadata を渡す。File ID は世代更新で変わり得るため Git へ固定しない。

## Browser flow

PWA は `./data/manifest.json` を確認し、ローカル metadata の SHA-256 と比較する。

- 同一 SHA-256: ダウンロードしない
- 新版: `./data/jrdb_stats_mart.sqlite` を取得
- 取得後: size / SHA-256 / required tables / `PRAGMA integrity_check` を検証
- 検証成功: incoming -> previous/current の順で安全に切替
- 検証失敗: current.sqlite を維持

Service Worker は `/data/` をキャッシュしない。SQLite のオフライン利用は OPFS の current.sqlite を使う。

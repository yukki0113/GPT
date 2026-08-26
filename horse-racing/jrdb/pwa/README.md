# JRDB 検証ラボ PWA

JRDBデータをスマホ端末へ保存し、競馬場など通信が不安定な場所でも条件集計できるオフライン PWA のフロントエンド正本です。

## Deployment

GitHub Pages は GitHub Actions 方式を使用します。

- source: `horse-racing/jrdb/pwa/`
- UI workflow: `.github/workflows/jrdb_pwa_pages.yml`
- Stats Mart data publish workflow: `.github/workflows/jrdb_pwa_publish_data.yml`
- Fact Lite publish workflow: `.github/workflows/jrdb_pwa_fact_lite_publish.yml`
- target branch: `main`
- default Pages URL: `https://yukki0113.github.io/GPT/`
- Fact Lite PoC: `https://yukki0113.github.io/GPT/fact-lite.html`

`pwa/**` または Pages workflow が `main` で更新されると自動デプロイします。

## Current phase

OPFS / sql.js / remote manifest /安全な自動同期を実機で確認済みです。

現在は、軸別事前集計の Stats Mart に加え、1出走1行の PWA専用 Fact Lite を並行検証しています。

Fact Lite は自由な `WHERE / GROUP BY` を主目的とし、種牡馬・母父・騎手・枠・脚質・年齢・性別・人気帯などを同一SQLite上で横断集計できます。

実装済み:

- mobile-first UI
- Web App Manifest
- Service Worker
- app shell の事前キャッシュ
- online / offline 表示
- OPFS 利用可否チェック
- sql.js 1.14.1 + WASM の固定version利用
- sql.js / WASM の同一origin配信・Service Workerキャッシュ
- remote manifest による最新版確認
- size / SHA-256 / schema / required tables / integrity validation
- `incoming.sqlite` / `previous.sqlite` / `current.sqlite` による安全な全量差し替え
- GitHub Release を利用したGit非管理の配布キャッシュ
- Google Drive -> Issue -> Actions -> Release -> Pages artifact の配布経路
- Stats Mart: 種牡馬 / 騎手 / 枠の集計
- Fact Lite: 種牡馬 / 母父 / 騎手 / 枠 / 脚質 / 年齢 / 性別 / 人気帯の集計
- 年 / 競馬場 / 芝ダ障害 / 距離 / 馬場状態 / 年齢 / 性別 / 人気帯 / 脚質 / 最低出走数フィルタ
- 勝率 / 複勝率 / 単勝回収率 / 複勝回収率表示
- Fact Lite 検索条件クリア

未実装 / 今後:

- Fact Liteを正式主DBとするかの最終設計反映
- 必要な追加条件・集計軸
- UIの最終調整
- データ生成から配布Issue作成までの完全自動連携

## Real-device validation

### Stats Mart

2026-08-26 に iOS版Google Chromeで Stats Mart v1.1 を検証しました。

- SQLite size: 約53.6 MiB
- OPFS保存: 成功
- 保存体感: 約1〜2秒
- ページ再起動後のOPFS自動復元: 成功
- 種牡馬 / 騎手 / 枠の集計: 成功
- 条件変更: 成功
- 機内モードでのPWA起動: 成功
- 機内モードでのOPFS復元・集計: 成功

### Fact Lite v0.1

同日、iOS版Google Chromeで Fact Lite v0.1 を検証しました。

- rows: 513,512
- SQLite size: 49,700,864 bytes（約47.4 MiB）
- 初回取得・読込体感: 約2〜3秒
- OPFS保存・自動復元: 成功
- 全期間集計:
  - 種牡馬: 約370 ms
  - 母父: 約348 ms
  - 騎手: 約310 ms
- 東京・芝・1600m:
  - 種牡馬: 約65 ms
  - 母父: 約65 ms
  - 騎手: 約62 ms
- 東京・芝・1600m・3歳・牡・1〜3人気・先行:
  - 該当0件
  - 約52 ms
- 全期間集計では一瞬の待機感はあるが、実用上ストレスになる水準ではないことを実機確認

この結果から、Fact Lite を自由条件集計の主DBとし、Stats Mart は必要な箇所だけ高速化用途で補助する構成が有力です。

## Distribution flow

大容量SQLiteはGitへcommitしません。

```text
Google Drive Analysis / Stats Mart
  -> dedicated Issue
  -> GitHub Actions
  -> build / size / SHA-256 / SQLite validation
  -> GitHub Release asset (distribution cache)
  -> GitHub Pages artifact /data/
  -> PWA manifest sync
  -> OPFS current.sqlite
```

Google Drive File IDは世代更新で変わり得るためGitへ固定しません。Issue本文だけでその時点のFile IDとartifact metadataを渡します。

通常のPWAコード更新時は `.github/workflows/jrdb_pwa_pages.yml` が現行Release assetをPages artifactへ再同梱するため、UI更新で配布DBが消えない構成です。

詳細は `SYNC_PROVIDER.md` を参照してください。

## Local sync behavior

PWA起動時はネットワークより先に OPFS `current.sqlite` を復元します。

オンライン時のみmanifestを確認し、ローカル metadata の SHA-256 と比較します。

- 同一SHA-256: 再ダウンロードしない
- 新版: 配布SQLiteを取得
- 取得後: size / SHA-256 / SQLite validation
- validation成功: incoming -> previous/current の順で切替
- validation失敗: current.sqlite を維持

Service Workerは `/data/` をキャッシュしません。オフライン利用は OPFS の current.sqlite を使います。

## Current Stats Mart distribution artifact

2026-08-26 のDrive実ファイルをActionsから再取得して検証した結果:

- source filename: `jrdb_stats_mart_2016_2026YTD_20260823_v1_1.sqlite`
- size: `56,254,464 bytes`
- SHA-256: `1d1798315646996991487c6e0cd5ee40ab330da58a8f77f6950694959a2b9f50`
- required tables: PASS
- `PRAGMA integrity_check`: `ok`
- Release tag: `jrdb-stats-mart-current`

従来READMEに記録されていたSHA-256とは差異があったため、配布workflowではDrive実ファイルを再取得し、実artifactのsize / SHA-256 / SQLite内容を検証した値を採用しています。

## Data policy

JRDB Raw、Analysis Lite、Stats Mart、Fact Lite の生成正本は引き続き Git 管理外です。
GitHub Release / GitHub Pages artifact に置くSQLiteは **PWA配信用キャッシュ** であり、Git正本ではありません。

詳細設計は `../docs/JRDB_PWA_Offline_Sync_Design.md`、実配布方式は `SYNC_PROVIDER.md` を参照してください。

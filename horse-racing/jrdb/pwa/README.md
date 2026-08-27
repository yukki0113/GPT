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

OPFS / sql.js / remote manifest / 安全な自動同期をiOS実機で確認済みです。

自由条件集計の主DB候補を **Fact Lite v0.2** とし、Stats Mart は将来必要になる重い集計だけを補助する位置づけへ寄せています。

Fact Liteは1出走1行を保持するため、条件を重ねても同一SQLite上で自由に `WHERE / GROUP BY` できます。

実装済み:

- mobile-first UI
- Web App Manifest
- Service Worker / app shell cache
- online / offline 表示
- OPFS 永続保存・自動復元
- sql.js 1.14.1 + WASM の同一origin配信
- remote manifest による最新版確認
- size / SHA-256 / schema / required tables / integrity validation
- `incoming.sqlite` / `previous.sqlite` / `current.sqlite` による安全な全量差し替え
- GitHub Release を利用したGit非管理の配布キャッシュ
- Google Drive -> Issue -> Actions -> Release -> Pages artifact の配布経路
- Fact Lite集計軸: 種牡馬 / 騎手 / 枠 / 脚質 / 年齢 / 性別 / 人気 / 前走距離 / 前走クラス
- 検索条件: 年From-To / 月From-To / 競馬場 / 芝ダ障害 / 距離From-To / 馬場状態 / クラス / レース名 / 最低出走数
- 年 / 月 / 距離のFrom-Toは同一行で横並び表示
- レース名部分一致UI（source dataのrace_name有無で自動有効化）
- 勝率 / 複勝率 / 単勝回収率 / 複勝回収率表示
- 検索条件クリア

### Month range semantics

- Fromのみ: 指定月以上
- Toのみ: 指定月以下
- From <= To: 範囲内
- From > To: 年またぎ扱い。例 `11月 -> 2月` は11,12,1,2月

### Previous-distance axis

`current_distance - previous_distance` をFact生成時に派生します。

- 正: 距離延長
- 0: 同距離
- 負: 距離短縮
- NULL: 前走不明

### Previous-class axis

前走 `grade_code` / `race_condition_code` から、新馬・未勝利・1勝・2勝・3勝・オープン・L・G3・G2・G1等へ分類します。Analysis内で前走を解決できない場合は推測せず「前走不明」です。

### Current-class filter

現走の `grade_code` / `race_condition_code` を前走クラスと同じ分類規則で、新馬・未勝利・1勝・2勝・3勝・オープン・L・G3・G2・G1等へ分類し、検索条件として利用します。

Fact Lite v0.2 SQLiteには両列が既に収録されているため、この検索条件追加だけではSQLite再生成を必要としません。たとえば `東京 / 芝 / 1600m / 2勝クラス` を指定し、集計軸を「脚質」にするとクラス限定の脚質傾向を確認できます。

### Popularity and previous-distance axes

集計軸「人気」は1〜9人気を個別カテゴリ、10番人気以下を `10～` にまとめます。人気は検索条件としては持たせません。

旧表示名「距離変化」は「前走距離」へ変更し、内部区分（距離延長 / 同距離 / 距離短縮 / 前走不明）は維持します。

## Race-name search status

Analysis Lite v1.2自体には `race_name` 列がないため、現行 Fact Lite v0.2.1は配布時にBAC由来のrace-name lookupを併用して `dim_race.race_name` へ収録します。現行配布では9,920レースのレース名を利用できます。

PWA側はSQLite内の実データを検出してレース名入力欄を自動有効化し、部分一致で絞り込みます。

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

### Fact Lite v0.1 baseline

2026-08-27、iOS版Google Chromeで検証しました。

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
- 全期間集計では一瞬の待機感はあるが、実用上ストレスになる水準ではないことを確認

この結果を根拠に、Fact Liteを自由条件集計の主DB候補とします。

### Fact Lite v0.2 current-class filter

2026-08-27、iOS版Google Chromeで `東京 / 芝 / 1600m / 2勝クラス -> 脚質` の集計を実行し、正常動作と実用上問題ないレスポンスを確認しました。

## Current Fact Lite v0.2 distribution

現行Analysis Lite v1.2から生成・配布済み:

- data version: `2016_2026YTD_20260823_v0_2_1`
- rows: 513,512
- size: `62,423,040 bytes`（約59.5 MiB）
- SHA-256: `279374cbd5e1e26f5d51b2cc03e5126c28c05d88da7a844b775c977dcec004ca`
- schema version: `0.2`
- Release tag: `jrdb-pwa-fact-lite-current`
- race-name search: race-name lookupを併用し9,920レースで有効

v0.2のクラス検索についてiOS実機で正常動作・実用上問題ないレスポンスを確認済みです。

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

v0.2 UIがv0.1保存DBを検出した場合は旧DBを利用状態にせず、オンラインならmanifest確認後にv0.2を自動同期します。

オンライン時のみmanifestを確認し、ローカル metadata の SHA-256 と比較します。

- 同一SHA-256: 再ダウンロードしない
- 新版: 配布SQLiteを取得
- 取得後: size / SHA-256 / SQLite validation
- validation成功: incoming -> previous/current の順で切替
- validation失敗: current.sqlite を維持

Service Workerは `/data/` をキャッシュしません。オフライン利用は OPFS の current.sqlite を使います。

## Current Stats Mart distribution artifact

- source filename: `jrdb_stats_mart_2016_2026YTD_20260823_v1_1.sqlite`
- size: `56,254,464 bytes`
- SHA-256: `1d1798315646996991487c6e0cd5ee40ab330da58a8f77f6950694959a2b9f50`
- required tables: PASS
- `PRAGMA integrity_check`: `ok`
- Release tag: `jrdb-stats-mart-current`

## Data policy

JRDB Raw、Analysis Lite、Stats Mart、Fact Lite の生成正本は引き続き Git 管理外です。
GitHub Release / GitHub Pages artifact に置くSQLiteは **PWA配信用キャッシュ** であり、Git正本ではありません。

詳細設計は `../docs/JRDB_PWA_Offline_Sync_Design.md`、実配布方式は `SYNC_PROVIDER.md` を参照してください。

# JRDB PWA Offline Sync Design

## 1. Purpose

JRDB Analysis Lite / Stats Mart を利用し、競馬場など通信が不安定な場所でもスマホだけで条件集計できる PWA を構築する。

旧 JRA-VAN 版「検証ラボ」の UI / 条件集計思想は再利用するが、SQLite の扱いは次の方式へ変更する。

```text
旧方式
ユーザーが SQLite を手動ダウンロード
  -> PWA でファイル選択
  -> sql.js でメモリ読込

新方式
共有ストレージ上の最新版を確認
  -> PWA が必要時だけ同期
  -> 端末内へ永続保存
  -> 通常利用は端末内 SQLite を直接使用
```

主目的は「SQLite を扱う操作」をユーザーから隠し、通常は PWA を開いて集計するだけの運用にすること。

---

## 2. 基本方針

### 2.1 データ正本

- JRDB Raw ZIP / Analysis Lite / Stats Mart の大容量 artifact は Git 管理外。
- Git には Python / SQL / schema / docs / PWA ソースのみを置く。
- 外部ストレージ側の File ID / URL は世代更新で変わり得るため、Gitへ個別 ID を固定しない。
- PWA は固定名 manifest または同期プロバイダ経由で「現在の配布版」を解決する。

### 2.2 端末配布対象

MVP の通常配布 DB は **Stats Mart** とする。

現行参考値:

- Analysis Lite v1.2: 約 188 MB / 513,512 行
- Stats Mart v1.1: 約 54 MB

Analysis Lite は Mart 生成・詳細分析・開発側の基盤として保持し、スマホ常用 DB にはしない。

### 2.3 オフライン優先

- PWA 起動時はネットワークを待たず、端末内の前回同期済み SQLite があれば即利用可能にする。
- 最新版確認はバックグラウンドで行う。
- ネットワークがない場合でも、最後に同期した DB で全条件集計を継続できる。

---

## 3. 全体アーキテクチャ

```text
JRDB Raw
   |
   v
Analysis Lite
   |
   v
Stats Mart
   |
   +--------------------------+
   | 外部ストレージ           |
   | (Google Drive 等)        |
   | - current manifest       |
   | - SQLite artifact        |
   +-------------+------------+
                 |
                 | sync
                 v
+---------------------------------------+
| GitHub Pages PWA                      |
|                                       |
| Service Worker                        |
|   - HTML / JS / CSS                   |
|   - sql.js / wasm                     |
|                                       |
| App                                   |
|   - Sync Manager                      |
|   - DB Manager                        |
|   - Query Builder                     |
|   - Stats Renderer                    |
|                                       |
| OPFS / browser private storage        |
|   - jrdb_stats_mart.sqlite            |
|   - jrdb_stats_mart.previous.sqlite   |
|   - sync metadata                     |
+---------------------------------------+
```

GitHub Pages には UI と実行コードだけを配置し、JRDB データ本体は置かない。

---

## 4. PWA 内部ストレージ

### 4.1 SQLite 保存先

第一候補は OPFS (Origin Private File System)。

```text
/jrdb/
  current.sqlite
  previous.sqlite
  incoming.sqlite
```

役割:

- `current.sqlite`: 現在使用中
- `previous.sqlite`: 更新失敗時のロールバック用
- `incoming.sqlite`: ダウンロード / 検証中

ユーザーが通常の「ダウンロード」フォルダから SQLite を探す運用にはしない。

### 4.2 同期メタデータ

SQLite 本体とは別に軽量メタデータを保持する。

例:

```json
{
  "artifact_type": "jrdb_stats_mart",
  "schema_version": "1.1",
  "data_version": "2016_2026YTD_20260823",
  "updated_at": "2026-08-23T23:59:59+09:00",
  "size": 56200000,
  "sha256": "...",
  "local_status": "ready"
}
```

保存先は IndexedDB または OPFS 上の JSON とし、SQLite を開かなくても最新版比較できるようにする。

---

## 5. 配布 manifest

同期元は「固定 URL / 固定名の manifest」を提供することを基本とする。

例:

```json
{
  "artifact_type": "jrdb_stats_mart",
  "schema_version": "1.1",
  "data_version": "2016_2026YTD_20260823",
  "period_from": "2016-01-01",
  "period_to": "2026-08-23",
  "size": 56200000,
  "sha256": "...",
  "download": {
    "provider": "google_drive",
    "locator": "logical-name-or-provider-key"
  }
}
```

重要:

- Git に変動する Google Drive File ID を固定しない。
- manifest から同期プロバイダが実ファイルを解決する。
- `schema_version` と `sha256` を必須項目とする。
- PWA は schema 非互換版を無条件で置き換えない。

---

## 6. 起動フロー

### 6.1 通常起動

```text
PWA起動
  |
  +-> Service Worker cache から UI 起動
  |
  +-> current.sqlite 有無確認
        |
        +-> あり: 即DBを開いて集計可能
        |
        +-> なし: 初回セットアップ画面
  |
  +-> ネットワーク利用可能なら manifest 確認
        |
        +-> 同版: 何もしない
        |
        +-> 新版: 「更新あり」を表示
```

**ローカル DB の起動を manifest 取得より優先する。**

競馬場でネットが繋がらなくても、起動処理がネットワーク待ちで止まらないようにする。

### 6.2 初回

```text
PWAインストール / 初回起動
  -> 同期元へ接続
  -> manifest取得
  -> SQLite取得
  -> incoming.sqliteへ保存
  -> 検証
  -> current.sqliteへ昇格
  -> 集計画面利用可能
```

---

## 7. DB 更新フロー

SQLite の更新は直接 `current.sqlite` を上書きしない。

```text
最新版検知
  -> incoming.sqlite にダウンロード
  -> size確認
  -> SHA-256確認
  -> SQLiteオープン確認
  -> schema version確認
  -> PRAGMA integrity_check
  -> 必須テーブル確認
  -> current -> previous
  -> incoming -> current
  -> local metadata更新
```

途中で失敗した場合は `current.sqlite` を残し、旧版をそのまま利用する。

MVP では「差分パッチ」ではなく **SQLite 全量差し替え** とする。

約 50 MB 台の Mart であれば、更新頻度が開催終了単位である限り、実装単純性と復旧容易性を優先する。

---

## 8. 同期方式

同期処理はプロバイダ依存部分を分離する。

```text
SyncProvider
  - getManifest()
  - openDownloadStream()
  - authenticateIfNeeded()
```

### 8.1 Google Drive

現在の大容量 SQLite の保管先として利用中。

直接 PWA から Drive を利用する場合は、認証 / CORS / ダウンロード URL の有効期限等を考慮する必要がある。

そのため PWA 本体へ特定 File ID や秘密情報を埋め込まず、以下のいずれかで実装する。

1. Google Drive OAuth を利用する `GoogleDriveSyncProvider`
2. 安定した manifest / resolver を介して Drive 上の最新版を解決する
3. 将来別ストレージへ移行しても `SyncProvider` だけ差し替える

MVP の設計上は Google Drive を前提にしつつ、フロントの集計ロジックとは結合しない。

---

## 9. Service Worker / オフライン資産

旧版は sql.js を CDN から読み込んでいたが、オフライン利用を主目的にする新PWAでは、実行に必要な資産も Service Worker でキャッシュする。

対象:

- `index.html`
- CSS
- JS
- PWA manifest
- icon
- sql.js JavaScript
- sql.js WASM

これにより、ネットワーク断時でも UI と SQLite エンジンの両方を起動できるようにする。

---

## 10. データアクセス方針

### 10.1 MVP

PWA から参照する通常 DB は Stats Mart のみ。

現行 v1.1:

- `mart_sire_yearly`
- `mart_jockey_yearly`
- `mart_frame_yearly`

共通条件:

- year
- venue_code
- track_type
- distance
- track_condition_code

共通集計値:

- starts
- wins
- seconds
- thirds
- top3
- win_payout_sum
- place_payout_sum

### 10.2 指標

PWA 側で共通計算する。

```text
勝率       = wins / starts
連対率     = (wins + seconds) / starts
複勝率     = top3 / starts
単勝回収率 = win_payout_sum / (starts * 100)
複勝回収率 = place_payout_sum / (starts * 100)
```

最低出走数フィルタは集計後の `HAVING starts >= ?` で処理する。

---

## 11. Mart 拡張方針

現行 Mart にない軸は、まず Analysis Lite を基に Mart 追加時の行数 / サイズ / 集計速度を計測する。

優先候補:

1. running_style
2. broodmare_sire_name
3. sire_line_code
4. final_win_popularity 帯
5. training_index 帯
6. distance_aptitude
7. uptrend
8. race_condition_code
9. age
10. sex_code

PWA の全条件を Analysis 直読みで解決するのではなく、**スマホで頻繁に使う集計軸は Mart 化する**。

Mart は軸別テーブルを維持し、巨大な多次元クロス集計テーブルにはしない。

---

## 12. UI 方針

旧「検証ラボ」から以下を継承する。

- カード型UI
- 条件入力 → 実行 → 結果の単純な流れ
- スマホ縦持ち優先
- 詳細 / 監査情報は `<details>` に収納

新規追加:

### DBステータス領域

通常は簡潔に表示する。

```text
データ: 2016 - 2026/08/23
同期: 2026/08/24 07:10
状態: オフライン利用可
```

操作:

- `最新版を確認`
- `今すぐ同期`
- `DB情報`

SQLite のファイル選択UIは通常画面から撤去する。

復旧用として「手動 SQLite インポート」は詳細メニュー内に残してもよい。

---

## 13. PWA コード構成案

新PWAは `horse-racing/jrdb/pwa/` を正本候補とする。

```text
horse-racing/jrdb/pwa/
  index.html
  manifest.webmanifest
  service-worker.js
  css/
    app.css
  js/
    app.js
    db-manager.js
    sync-manager.js
    sync-provider.js
    query-builder.js
    stats-defs.js
    renderer.js
  vendor/
    sql-wasm.js
    sql-wasm.wasm
  icons/
```

旧 `horse-racing/legacy/kenshow_labo_jravan/docs/` は凍結したまま変更しない。

GitHub Pages への実配信パスは repository の Pages 設定を確認したうえで決定する。

---

## 14. MVP 機能

Phase 1 の完成条件:

1. PWA シェルがオフライン起動する
2. Stats Mart を端末へ一度保存できる
3. 2回目以降はファイル選択なしで DB が開く
4. ネット断でも集計できる
5. manifest で新旧判定できる
6. 更新失敗時も旧DBを継続利用できる
7. 種牡馬 / 騎手 / 枠の3タブで集計できる
8. 年 / 場 / 芝ダ / 距離 / 馬場状態 / 最低出走数で絞れる
9. 勝率 / 連対率 / 複勝率 / 単勝回収率 / 複勝回収率を表示する
10. DB対象期間と最終同期時刻を画面で確認できる

---

## 15. Phase 2 以降

- Mart集計軸追加
- 保存フィルタ
- 複数条件プリセット
- 前走条件集計
- 競走条件 / グレード等のフィルタ追加
- 同期自動化の高度化
- 配布 SQLite の分割検証
- Analysis Lite を利用する高度検索画面の別モード化
- ローカルのメモ / 注釈を別DBまたはIndexedDBへ保存

共有 Mart SQLite 自体は原則 read-only とし、個人メモ等の端末側更新情報は分離する。

---

## 16. 設計上の重要判断

### 継承するもの

- 「検証ラボ」という用途
- スマホで自由条件集計
- sql.js / SQLite を利用するブラウザ内集計
- UIはGitHub Pagesで配信
- データは端末内で利用

### 作り直すもの

- 手動ファイル選択を前提とした DB ロード
- CDN 接続を前提とした sql.js 読込
- JRA-VAN / SQL Server 固有 schema
- レース一覧 / 競馬新聞中心の旧画面構成

### 新たに中心にするもの

- Stats Mart
- 自動同期
- OPFS永続化
- Service Workerによる完全オフライン起動
- manifest + SHA-256 + schema version による安全な差し替え

---

## 17. 実装順

```text
1. PWA配置先 / GitHub Pages配信方式の確定
2. 新PWA skeleton作成
3. sql.js / WASMのローカル配信化
4. OPFS DB Manager
5. 手動インポートで Stats Mart 読込PoC
6. 現行3 Martの集計UI
7. Service Worker / オフライン起動
8. manifest / Sync Manager
9. Google Drive SyncProvider
10. スマホ実機で50MB級SQLiteの同期・起動・集計測定
11. 結果を基にMart拡張判断
```

最初から Drive 同期だけに依存せず、Step 5 の手動インポート経路を復旧手段兼PoCとして先に成立させる。通常運用では最終的に自動同期を利用する。

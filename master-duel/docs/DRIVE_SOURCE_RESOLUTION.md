# Google Drive 原データ探索・復元運用（Master Duel）

- 策定: 2026-11-09
- 正本: GitHub `yukki0113/GPT` の本書、監査正本 `audits/p0_202611/`
- 原データ実体: Google Drive（指定フォルダ）。公開GitHubにはカード全文JSONをコミットしない。
- 参照モデル: 中央競馬JRDBの `horse-racing/jrdb/docs/JRDB_2026_Raw_Drive_Reference.md`、`JRDB_Store_Resolver_v0_1.md`、`horse-racing/jrdb/.gpt/WORKFLOW.md`。**Drive先行の所在解決・再確認・サイズ/SHA検証**の原則のみ採用し、中央競馬固有のActions/データ取り込み処理は流用しない。

## 1. 固定フォルダ・既存ファイル（2026-11-09 実確認）

正本ソースフォルダ:

- URL: https://drive.google.com/drive/folders/1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh
- Drive folder ID: `1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh`
- Drive folder name（確認時）: `source`

| 役割 | ファイル名 | Drive File ID（確認時） | byte size | 監査済みSHA-256 |
|---|---|---|---:|---|
| MD全件候補 | `master-duel-raw.json` | `1pCsiJzG6_NLZE5FI5TVQhmycbmwHqEJ1` | 83,388,036 | `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b` |
| OCG/TCG全件候補 | `cards.json` | `1yOaH4JWCdpG7XYBqeMDRegbJ3mxUzYc1` | 110,258,836 | `5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7` |
| MD禁止制限（施行日2026-11-05） | `current.vector.json` | `1oIAom4ABwXaLDw3a_K6aqL-pYFi5FTJ5` | 3,395 | `2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781` |

**検証の水準に注意**: 2026-11-09にGoogle Driveネイティブコネクタでフォルダメタデータ・直下ファイル一覧・ファイル名・ID・byte sizeを**実確認**。過去にユーザーが別途添付した原本のSHAを掲載している。**この確認ターンでDriveの3ファイルを再ダウンロードしてSHA照合したわけではない**ので、「Drive上の全バイトのSHA一致確認済み」とは言わない。

個別ファイルIDは今回の探索を確実にする**フォールバックの照合対象**。ユーザーがDrive上で差し替えれば変わりうるため、名称・親フォルダ・ファイルメタデータを再確認する。将来の版は日付・SHA付きの追補として別途記録し、古い版を黙って「現在版」としない。

## 2. ファイル探索の必須順序（「見つからない」報告前に実施）

1. **Git正本を読む**。この文書、`master-duel/.gpt/CONTEXT.md`、`WORKFLOW.md`、`audits/p0_202611/P0_SOURCE_ARCHIVE_MANIFEST.md`を読む。過去会話や一時添付の保存状態に依存しない。
2. **DriveコネクタによるフォルダID直指定**: `get_file_metadata(fileId="1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh")` でフォルダの実在、名前、権限を確認する。
3. **フォルダ直下一覧**: `list_folder(url="https://drive.google.com/drive/folders/1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh", top_k=100)` を実行。少なくとも目的ファイル名、タイプ、サイズを確認する。フォルダが大きい・一覧が不完全な場合はページング等を考慮し、表示上位だけで欠損と断言しない。
4. **完全一致名と個別File IDを照合**: 見つかれば候補のメタデータを直接読む。ファイル名が変更された場合は上表のFile IDでも `get_file_metadata` を試し、親フォルダ・サイズ・名前を再確認する。
5. **代替検索**: フォルダ内に見つからなければ `Google_Drive.search(query="master-duel-raw")` / `cards.json` / `current.vector.json` 等で名称の前方一致・表記差・移動先を検索。必要なら `special_filter_query_str="'1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh' in parents"` を使う。複数候補は名前だけで選択せず、File ID・mimeType・サイズ・親・更新日時を照合する。
6. **歴史的な場所も検査**: フォルダ内の`old/`（確認時フォルダID `1VNWBPD1oplJwCjIhy4M491jcm_aBCLSr`）や過去監査記録を検索。ただしユーザー指定の現行3ファイルを上書きしない。
7. **接続・アクセスの再判定**: Driveコネクタの認可切れ、API・ネットワーク制限、トップK制限、検索結果の未反映（インデックス遅延）を「本当に不存在」と区別する。特に**検索0件 ≠ ファイル不存在**。既知File IDのメタデータ取得が成功した場合、名前検索が失敗してもそのファイルを「ない」と報告しない。
8. **最後に報告**: (a) found+metadata-verified、(b) found+download-hash-verified、(c) inaccessible、(d) search-inconclusive、(e) verified-absent のいずれかを使い、どの経路を何時に確認したかを記載。**少なくともフォルダID直指定と個別ID照合を試さず「不存在」と断言しない**。

### ダウンロード・内容検証

- Driveから読み出す場合、**認証済みGoogle Driveコネクタ**のメタデータ取得後、非GoogleネイティブのJSONを `fetch(url=<Drive URL>, download_raw_file=true)` などサポートされるダウンロード経路で取得する。必要に応じてmaterializeする。巨大ファイルはベストエフォートのテキスト全文取得を避ける。
- 取得した**バイト列のサイズとSHA-256が上表と一致**して初めて、2026-11-09に監査したスナップショットとして使用する。異なれば破損扱いとは限らず、改訂版・更新差分の可能性も評価し**別バージョン**として保留する。
- ダウンロード不可やタイムアウトなら、検索ミスと混同せず、`metadata-visible / download-blocked`として記録。ユーザーに再アップロードを依頼するのは既知File IDを含むアクセス経路を試した**後**。
- 二次公開・継続保存・利用条件が確定するまで、公開Git、公開Issue、Actionsログへカード効果全文や元JSONを転記しない。

## 3. 更新時の原則

- GitHub: 基本設計・実装・正本運用指示・監査ハッシュ/coverage。Google Drive: **元JSONの実体保存先**。
- 同名JSONを最新版と断定しない。`current.vector.json` の適用日は**内容の`date`を検査**。2026-11-05は今回の固定スナップショットであって恒久的な現行規制ではない。
- 更新後は、元ファイル名、Drive File ID、byte数、SHA-256、取得/照合時刻、データ内の施行日、元配布版をmanifestへ記録。過去スナップショットのハッシュを上書きしない。
- Driveとローカル/Chat添付は別の保存面。会話添付の期限切れを、Drive原本がないことの根拠にしない。
- 中央競馬プロジェクトと同様に**既存Drive資産の発見・再利用が先**。再ダウンロードや外部ソース再取得は不足または不整合が確認できた場合だけ。
- GitHub ActionsからDriveを認証付きで参照・書込しない（リポジトリ共通 `.gpt/GITHUB_OPERATION_POLICY.md` §9.1）。Chat/WorkのネイティブDriveコネクタを利用。未認証の公開read-onlyルートを使うなら共通のSHA固定済みマニフェスト＋`tools/gpt_io/public_drive/fetch.py` の承認済み経路が必要。

## 4. 共有設定の注意（2026-11-09メタデータ確認）

このフォルダの共有権限には **`anyone: reader`**（リンクを知っている全員が閲覧可）が含まれていた。**Drive上に存在する＝非公開ではない**。権利条件が未確定のカード全文を扱うため、**公開を避けるならDrive側の共有設定を「制限付き」に変更することを推奨**。この監査では共有設定を変更していない。ファイル単位の公開範囲は別途メタデータで確認する。

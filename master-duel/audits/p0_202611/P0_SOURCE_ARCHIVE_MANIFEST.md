# P0原データ保管マニフェスト（2026-11-09）

> **Drive保管先確定（2026-11-09）**: 原JSON3ファイルはGoogle Drive [sourceフォルダ](https://drive.google.com/drive/folders/1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh) に保存済みであることを、Driveネイティブコネクタのメタデータ/直下一覧で確認。各ファイル名・File ID・サイズは [探索運用正本](../../docs/DRIVE_SOURCE_RESOLUTION.md) を参照。**Drive上のバイト列をダウンロードしてSHA照合したわけではない**。既存の「非公開リモート未保存」は**GitHubについての状態**であり、現在はDrive上に元ファイルが存在する。フォルダおよび親フォルダの現行共有設定はユーザーが正式承認済み。**制限付き変更の推奨・反復警告はしない**。個別File IDは更新ごとに変わるため恒久参照しない。


> **最新状態（2026-11-09 / 3ファイル版追加）**: `master-duel-raw.json` / `cards.json` に加えて、2026-11-05施行の `current.vector.json`（3,395 bytes / SHA-256 `2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781`）をローカルGitに記録。**新しい保管用Git bundle**: `master_duel_P0_source_snapshot_20261109_3files.bundle` / 31,995,530 bytes / SHA-256 `4f7bc96bdfe2ed7968d1dfab7d8841404dc0e1d6792cba5bd3ebd2a239826679` / 内部commit `d627a0a258e2bc611b3e77284989dafd50c2fb67`。復元検証: `git bundle verify` PASS、3JSONのgit object復元SHA-256一致。**公開GitHubに元JSONは置いていない。非公開リモートにも未アップロード**。古い2ファイルbundleの情報は履歴として以下に保存。 [禁止制限監査](P0_LIMIT_REGULATION_AUDIT_20261109.md)。


## 目的
P0監査に用いたユーザー提供JSON **2ファイルの固定ハッシュ**と保管状態を記録する。

**重要**: この `yukki0113/GPT` は公開リポジトリである。日本語カードテキスト等を含むJSON原本は、当面二次公開しない方針と権利関係の未確認を踏まえて**ここにはコミットしない**。

## 入力元データ

| ファイル | バイト数 | SHA-256 |
|---|---:|---|
| `master-duel-raw.json` | 83,388,036 | `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b` |
| `cards.json` | 110,258,836 | `5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7` |

提供元候補：
- https://dawnbrandbots.github.io/yaml-yugi/master-duel-raw.json
- https://dawnbrandbots.github.io/yaml-yugi/cards.json

※ファイル自体はユーザーから2026-11-09に提供されたもの。配布元HTTPの生成版・ETag・原本との一致は独立未検証。

## Git保管用バンドル（公開GitHub未配置）

2ファイルの内容を、Gitコミット履歴として一つにまとめた **local Git bundle** を作成済み。

- バンドル名: `master_duel_P0_source_snapshot_20261109.bundle`
- バンドルサイズ: **31,994,238 bytes**
- バンドルSHA-256: `bf3fc68f59595c4355dd3d5e8fc31c96865479c73f048de04975e3abc35833c9`
- バンドル内 `main` コミット: `4e68d897edf1329fcec5348d5b5000b2dec22eb4`
- 収録パス: `sources/master-duel-raw.json`, `sources/cards.json`, `README.md`
- 検証: `git bundle verify` 成功。Gitオブジェクトから両JSONを復元してSHA-256一致を確認。
- **保管ステータス**: 対話環境で生成・ユーザーへバンドル添付。**非公開のリモートGitHubリポジトリへのアップロードは未実施**。

復元例：

```bash
git clone master_duel_P0_source_snapshot_20261109.bundle master-duel-p0-sources
cd master-duel-p0-sources
sha256sum sources/master-duel-raw.json sources/cards.json
```

### 非公開リモート移行時の注意
- 現時点で認証接続から確認できるユーザー所有リポジトリは公開設定のみ。既存公開リポジトリやそのbranchへ原本をpushしない。
- `cards.json` は110,258,836 bytesで、GitHub通常Git blobの単一ファイル100 MiB上限を超える。**同じ履歴をそのままGitHubへpushする方法は不可**。Git LFS対応の非公開GitHub repo、あるいは別の非公開Gitホスト等の保管手段を選び、実際の移送後に独立読み戻しとSHA-256照合を行う。
- ローカルGit bundleは完全なGit履歴を保持するが、それ自体は**GitHubの遠隔保管ではない**。別途ユーザー側でバックアップするか、非公開の保管先を確保すること。
- コンテンツの著作権および長期保存・利用条件は未解決のため、外部公開や再配布はしない。

## 関連監査
- [MD全件JSON監査](P0_FULL_JSON_AUDIT_20261109.md)
- [日本語名突合監査](P0_JA_CROSSWALK_20261109.md)
- [P0判定](P0_DECISION.md)

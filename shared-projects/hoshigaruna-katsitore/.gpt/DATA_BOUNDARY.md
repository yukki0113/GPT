# DATA BOUNDARY

本ProjectにおけるGitHub / Google Drive / 外部管理sourceの境界を定義する。

## 1. GitHub

GitHubは、再利用可能かつテキスト中心の技術資産を正本とする。

例:
- source
- adapter
- schema
- config
- test
- docs
- 運用契約

本ProjectのGit rootは `shared-projects/hoshigaruna-katsitore/`。

## 2. Project Google Drive

共有Project用Driveは、メンバー間で共有するデータ資産を扱う。

例:
- Excel
- 共有原本
- 大容量ファイル
- 分析成果物
- Gitに置く必要のない日次資産

### 2.1 まきば回顧馬台帳

まきばの回顧馬台帳はGoogle Drive側を正本とする。

- file: `回顧馬.csv`
- Drive file ID: `1PLKLRwmwG5lIuzdfk6ABbCahwzNQEjBo`
- header: `日付,馬名,コメント`

GitHubへ同内容のCSVコピーを正本として置かない。
GitHub側は `docs/MAKIBA_REVIEW_HORSES.md` に保存形式・更新条件・参照契約のみを保持する。

このCSVは過去回顧馬検索、次走確認、競馬新聞等への紐付け時の共有原本として扱う。

## 3. Externally managed sources

Project外部で管理されるsourceが存在してよい。

共有Project側が依存する契約は、物理的な保存場所そのものではなく、次のいずれかとする。

- adapter
- normalized interface
- pointer / manifest
- Project用に提供されたasset

既存sourceの保存先を本Projectへ移すことを利用条件にしない。

## 4. User-facing disclosure boundary

外部管理sourceの物理ストレージURL、非共有path、認証情報、内部接続構成は、通常の共有チャットで必要となるProject interfaceではない。

GPTは通常の予想・分析・統合会話において、それらの内部情報を自発的に列挙・提示しない。

必要な場合は、

- 「外部管理source」
- 「管理側で接続済み」
- 「adapter / interface経由で利用」

等、利用者に必要な粒度で説明する。

内部保存場所そのものを使う管理作業が必要になった場合は、ホスト側の管理環境で扱う。虚偽の説明は行わず、共有利用に必要な範囲と内部実装詳細を分離する。

## 5. Secrets

API key、password、token、cookie、credential等の秘密情報をGitへ保存しない。

共有チャットにも貼り付けない。

Secretsを必要とする実行経路は、repository共通GitHub Operation Policyに従って設計する。

# M5-C C5 受入監査 — private ZIP/manifest と M6 ThemeKnowledgeBundle（2026-11-11）

## 完了範囲・判定

**C5 PASS（private側の知識ZIP+manifest・独立バイトSHA照合・検証状態付きM6入力アダプタ）**。これはM5-C側のインターフェース完了であり、M6のデッキ生成、MD現行規制監査、所有照会、必要CP、対戦実測の完成を意味しない。

- [C5実装](../engine_m5/private_bundle.py) の `make_sidecar` はC4知識、C3派生候補、必要ならC4 overlayの3メンバーから**固定日時・ソート順・Deflateの再現可能ZIP**を作成する。
- `open_sidecar` はZIP/manifest/MD SQLiteの**外部で保持した期待SHA256を必須**とし、受信したrawバイト、manifest内の各メンバーSHA/容量、JSON canonical文字列、C3→C4 lineage、レシピ/バリアント外部キー、規格、overlayのSHA・参照整合を拒否優先で検証する。manifestを攻撃者が同時に書き換え得る状況でmanifest内SHAを単独信頼しない。呼出側は既知のmanifest期待SHAを信頼済み台帳から渡す。
- `theme_knowledge_bundle` は単一テーマでプロフィール、出典、claim/recipe/routeの局所サブグラフ、コア/任意/汎用パッケージ、低レア候補、未解決主張/矛盾/失効情報を返す。**全テーマで `recommendation_eligible=false`、規制・所持・CP・ゲーム実測はいずれも未検証**とし、M6側の別ゲートを要求する。
- GitHubの公開域はコード/合成fixture/件数とSHAのみ。実記事ごとのデッキ個票、私有デッキ情報はprivate Driveのみに保持する。

## 実データの往復

C4実知識: `MD_M5C_C4_KNOWLEDGE_20261111.json` version4、58,611 bytes、SHA `511675bd541fe243ae79d9419b98caa13256922957294040103434f20b2d7db6`。元private card master SQLite SHA `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`。過去のC3知識SHA `8812f23d07b616168de9326d6c991e8f422aa68adfddb93b4a9b9414415a9be0` をlineage参照。C4の仮想差分リプレイを実際の変更とみなさないため、格納した失効overlayは`statuses=[]`。以後の差分はC4検証済みの新overlayを個別SHAで追加する運用。

| 非公開Drive成果物 | バイト | SHA256 | Drive ID |
|---|---:|---|---|
| `MD_M5C_C5_PRIVATE_SIDECAR_20261111.zip` | 14,172 | `f3a5c4798fb3ce8b4c78e9c9ea2a704ad34dfb5fb5eb70aea1c5c76c10d09e53` | `1QXZ6DoxseSEdwa0RQndmtpk1x_iI3uq0` |
| `MD_M5C_C5_PRIVATE_SIDECAR_MANIFEST_20261111.json` | 870 | `fddc571438e6692a826f99ada813e794027ae34ebc3059ddd1d771169a57b3db` | `1_gXTKrhEJMz46RwQk6uTph6uII4dspJi` |
| `MD_M5C_C5_PRIVATE_BUNDLE_AUDIT_20261111.json` | 1,398 | `b6e5c19f3f05c7dda866d193ab1018c30485f336a1efd05f3e42cd2dc0a90b25` | `1c8kyqGaeMh9LHRnnnazjUIbr-grVXyNO` |

3件を非公開DBフォルダに**新規**保存し、独立したDrive取得要求→生バイト一致→外部SHA一致→manifest ZIP内部3メンバーの解凍ハッシュ確認を実施。以前のC1–C4スナップショットは上書きしていない。

### プロフィール別 M6 アダプタ読み出し

| テーマ | claims | 掲載レシピ | 展開ルート | 低レア候補 | 主な保留事項 |
|---|---:|---:|---:|---:|---|
| イビルツイン | 2 | 1 | 1 | 0 | 掲載MAIN40と可視39の不整合 |
| 軍貫 | 2 | 1 | 0 | 1 | UR0は構成上のみ。M3・所有/CP・成立UNKNOWN |
| 海晶乙女 | 2 | 0 | 0 | 0 | 完全な掲載レシピ未取得 |
| ブラック・マジシャン | 2 | 0 | 0 | 0 | 中核URの負例。完全な掲載レシピ未取得 |
| スピードロイド | 2 | 0 | 2 | 0 | 展開2経路はTEXT_CHECKED、GAME_TESTEDではない |

全件でMD規制施行日`null`と`recommendation_eligible=false`。M6への入力は可能だが**推奨確定不可**。失効overlayにより対象claim/route/recipe/variantがSTALEまたはREVIEW_REQUIREDになった際は、M6は該当素材を検証済みとして採用せず再検証待ちにする。

## 合成回帰とセキュリティ

`engine_m5/tests/test_m5c_c5.py` は合成カード・架空記事だけを使用。固定ZIP再現性、差し替えZIP/manifest/期待SHA、内部ファイル不一致、カード数/3枚制限、再検証overlayの別知識参照、未知プロファイル、元構造非変更、掲載レシピ枚数不整合の保留、M6の不明項目ゲートを確認する。全体CIは別途Actionsログを正本とする。

## 運用・次工程

1. 統合元の本番 `MD_CURRENT_HEAD.json` を変更しない。これはカード/所持のHEADであり、知識sidecarのために昇格させない。
2. `MD_OWNED_DECK_CATALOG.json` を変更しない。ユーザー登録デッキは別系統。
3. C5 ZIPとmanifestは独立のprivate成果物。後続M6が読み込む際は**最新と呼ぶだけでは不十分**で、期待ZIP/manifest SHAと元DB SHAを信頼できる登録済み参照から明示して読み戻す。
4. 現行M6実装がないため本工程は**M6向け入力アダプタ**まで。完成レシピ生成はM6の開始工程で進める。

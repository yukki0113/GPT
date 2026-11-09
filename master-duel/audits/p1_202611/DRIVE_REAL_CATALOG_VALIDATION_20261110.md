# 実カードマスター検証ZIPのDrive配置・読み戻し（2026-11-10）

## 工程と判定

**限定GO：実カード13,948件の基本メタデータを含む検証用SQLite ZIPを、Driveの正規DBフォルダへ新規配置した。独立読み戻しとバイトSHA-256が一致し、SQLiteも整合。** ただし本番`MD_CURRENT_HEAD.json`は更新せず、カード本文・規制・パック・所持を正式に運用開始したわけではない。P1-A1の権利・公式照合ゲート、Driveのatomic CAS欠如、単一ライター限定を維持。

## 保存先と正本分離

- 保存先：Google Drive `GPT/MasterDuel/DB/`（既存の正式フォルダ）。
- 追加ファイル：`MD_CARD_MASTER_13948_PR2509_VALIDATION_ONLY_20261110.sqlite.zip`。
- 分類：`REAL_CARD_MASTER_VALIDATION_ONLY`。**本番HEAD・合成テストHEADのいずれにも紐付け・昇格しない**。既存ZIP/HEAD/manifestは変更しない。
- 共有状態：ファイルは `shared=false`、所有者のみ。保存先フォルダも以前の監査で非公開。
- 保存方法：不変の新規ファイルをアップロード（既存上書きなし）。
- 元ファイル・検証ZIPの実バイト列は公開Gitへコミットしない。Driveの個別ファイルIDは公開監査に記録しない。

## 固定SHAとダウンロード結果

- ZIP：**1,107,471 bytes**
- SHA-256：`e81920a247631c66f1fdc04b500c27644c273dcc6b3741e07450755f652c29d5`
- ZIP内ファイル：`master_duel.sqlite` 1件
- SQLite：**8,904,704 bytes**
- SQLite SHA-256：`6985929a3127415bf893998b4078ba7ef654320175d9498104e0c266fb807d8e`
- Drive新規アップロード後に**別のGoogle Drive fetch**で同ZIPを再取得し、ローカル原本とバイトSHA-256が一致（PASS）。

このSHAは今ターンに実際にアクセスした検証用ファイルのハッシュ。2026-11-10の先行PR監査レポートの「同じ役割の別途生成ZIP」とSHAが異なる場合、**今回のDrive保存版はこのSHAを正として扱う**。同じカード集合でもSQLiteページ配置・ZIPエンコード等でバイトが異なりうる。

## SQLite検査

`PRAGMA integrity_check=ok`、`PRAGMA foreign_key_check`=0件。

| テーブル | 件数 |
|---|---:|
| cards | 13,948 |
| card_attributes | 13,948 |
| md_catalog | 13,948 |
| inventory | 0 |
| inventory_history | 0 |
| card_texts | 0 |
| banlist_entries | 0 |

表示名重複は「カオス・ソルジャー」1組のみ（別`konami_id`2件）。`craftable=UNKNOWN` 13,931件、明示的`NO`17件。

## P3照合向けの読み取り専用スモーク

P1 `normalize_name` と同等のNFKC/casefold/空白除去規則で、検証ZIPを展開してSQLite `cards` 名称を照合（**P3 `voice_staging.preview` 関数そのものの実行ではない**）。

- `灰流うらら`：一意に解決
- `増殖するＧ`／`増殖するG`：同じKONAMI IDへ一意に解決
- `墓穴の指名者`：一意に解決
- `カオス・ソルジャー`：2候補 `AMBIGUOUS`
- `存在しない架空カード`：0候補 `UNRESOLVED`

## 運用上の次の受入条件

1. 公開Gitの全P1/P2/P3/P4回帰テストを**実依存で**再実行（PR #2509時の86件はフル独立実行未完了）。P3 `preview` 本体をこの実ZIPに対して呼び、実カード名の `RESOLVED` / `AMBIGUOUS` / `UNRESOLVED` と `can_apply` を確認する。
2. P1-A1ゲートを別判断するまで、検証ZIPを`MD_CURRENT_HEAD.json`へ昇格しない。入力版・権利・公式性を明示して採用可否を記録する。
3. 採用承認時のみ単一ライターのバックアップ・Drive新規ZIP・読み戻し・HEAD更新を実施。同時更新の原子性は保証されない。
4. 汎用カード／出張パーツ優先リストは別工程で策定。個人の所持情報を公開Gitへ格納しない。

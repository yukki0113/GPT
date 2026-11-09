# P3 正式統合試験・基本カードマスター本番採用ゲート判定 — 2026-11-10

## 結論

**P1-A0/P1/P2/P3/カードマスター変換器の正式依存による統合回帰：90/90 PASS、スキップ0。前工程のテスト未実行問題は解消。**

**基本カードマスターの非公開・検証用の読み取り：GO。 本番HEADへの採用：NO-GOを維持**（技術的不具合が理由ではなく、既存のP1-A1出典/利用条件ゲートが未解消であるため）。本番 `MD_CURRENT_HEAD.json` の世代は0、空DBのまま変更しない。所持・履歴を変更しない。

## 入力と実行環境

- GitHub `main` 基準コミット：`1561e3824de3a38a9df972bc44b4db313990073e`。
- GitHub公開コード＋テスト **24ファイル**を取得、各ファイルのGit blob SHAを照合して一致。テストランナーだけ新規追加（`tools/run_full_regression.py`）。
- Python 3.13、標準 `unittest`、ネットワークを必要としないローカル実行。
- Drive非公開検証ZIP：`GPT/MasterDuel/DB/MD_CARD_MASTER_13948_PR2509_VALIDATION_ONLY_20261110.sqlite.zip`、1,107,471バイト、SHA-256 `e81920a247631c66f1fdc04b500c27644c273dcc6b3741e07450755f652c29d5`。個別Drive IDと実データ本体は公開Gitに記録しない。
- 実JSON原本 `master-duel-raw.json` SHA-256 `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b` / `cards.json` SHA-256 `5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7`。両者は同系列の配布元であり独立した公式検証ではない。

## 実行結果

| suite | tests | skipped | result |
|---|---:|---:|---|
| p1_a0 | 47 | 0 | PASS |
| sqlite_store | 13 | 0 | PASS |
| zip_store | 9 | 0 | PASS |
| voice_staging | 12 | 0 | PASS |
| card_master_import | 9 | 0 | PASS |
| **TOTAL** | **90** | **0** | **PASS** |

合成fixture・例外・レアリティ・ZIP攻撃対策・所持UNKNOWN/0・再送/取消・P3バッチ拒否を含む。特にP3の `test_private_real_catalog_readonly_optional` をスキップせず、**実Drive検証ZIPを入力して正式な `voice_staging.preview()` に通した**。

再現方法（`master-duel/` 作業ディレクトリ）：

```bash
export MD_PRIVATE_REAL_CATALOG_ZIP=/private/path/validation.sqlite.zip
export MD_PRIVATE_REAL_CATALOG_ZIP_SHA256=e81920a247631c66f1fdc04b500c27644c273dcc6b3741e07450755f652c29d5
python tools/run_full_regression.py --require-real
```

ローカル実行に実カードのファイルがなければ `--require-real` を使わず合成テストのみ実行し、実データテストがskipになったことを報告する。上記環境変数を付けて実行した際はskip 0。

## 正式 P3 preview() での実カード読み取り

前工程の独立SQLite照合に加え、正式モジュール `voice_staging.preview` の呼び出しで以下を確認。

- 灰流うらら/増殖するG/墓穴の指名者：RESOLVED（現在の所持はUNKNOWN/NULL）。
- 増殖するＧ/増殖するG：同一カードへ正規化。
- カオス・ソルジャー：AMBIGUOUS（2候補）、同バッチ全件を適用不可。
- 存在しない架空カード：UNRESOLVED、適用不可。
- 同一カード二重指定：DUPLICATE_CARD_ID、適用不可。

**重要**：実カードZIPでのプレビューは、現行P3の「callerが渡すhead名/スコープ/ZIP SHA照合」契約を試すローカル読み取り専用テスト。実DriveのHEADを真正化していない。検証時の `SYNTHETIC_TEST` という擬似ターゲットは **実カードDBを合成データと分類して本番運用する意味ではない**。仮想ターゲットの `can_apply=true` は本番更新許可を意味しない。実Drive上のどのHEADも更新していない。

## 正式P1/P2モジュールでの実JSON一括変換

`python -m card_master_import` をGitHub正本の `sqlite_store.Store`, `zip_store.archive` とともに実行。互換アダプターを使っていない。

- `read_inputs` SHA固定照合 PASS、`dry_run` 13,948/13,948解決、完全一致13,931、正規化13、例外4、未解決/不正/重複0。
- `convert` 13,948件投入、`cards`/`card_attributes`/`md_catalog` 各13,948、`inventory`/`inventory_history`/`card_texts` 0。
- `PRAGMA integrity_check=ok`、`foreign_key_check` 空。
- 正式変換出力ZIP SHA `2443efc93e9c3ede7c7477518ba79f7e05bb892f4409f1add1c2591eec51b9f0`（1,107,471バイト）。既存Drive ZIPとはZIPの生成メタデータによりSHAが異なるが、**中身のSQLite SHA `6985929a3127415bf893998b4078ba7ef654320175d9498104e0c266fb807d8e` が完全一致**。
- 既存Drive ZIPを上書きしない。新たに生成したローカルZIPも公開GitHubへ保存しない。

## 採用ゲートと残留制約

技術受入はPASSとし、**P3正式統合の未完了項目は解消**。

本番採用は既存の `audits/p0_202611/P0_DECISION.md` / `docs/P1_A_LIMITED_GATE_DESIGN.md` のP1-A1 NO-GOを引き継ぐ。2026-11-09のゲーム内サンプル30件の照合は、**全13,948件の独立MD公式保証ではない**。YAML Yugi上流はカード効果文の権利帰属を明記し、コードライセンスとカードデータの権利は同一でない。日本の著作権法30条には私的使用の複製規定があるが、元配布元やゲームの個別利用条件に対する**包括的許諾の確認にはならない**。現在の成果物は効果全文・禁止制限・パック情報を格納していない。

**判定**：
- 非公開検証DBでの名称解決、差分の読み取り専用プレビュー、技術検証：限定GO。
- 本番 `MD_CURRENT_HEAD.json` を実データZIPへ切り替え、正式な個人所持台帳の書込先にすること：現時点NO-GO。
- 全文索引、外部再配布/公開Gitへのカードデータ転記、公式認証済みラベル：NO-GO。
- P2の`update_file`にatomic CASなし、単一ライター制約継続。

判定は現時点の実測範囲について完了しており、**技術試験が未実施という理由の保留は残していない**。本番化には別途「非公開の基本メタデータ限定での利用条件・責任範囲」の正式判断と単一ライターのHEAD切替手順が必要。

## 公開/非公開の境界

この監査文書・コード・架空fixtureのみGitHubへ置く。実JSON、実SQLite、個人所持データ、Driveファイルの操作用IDは非公開。Driveの既存本番HEAD・検証ZIPを破壊/変更しない。

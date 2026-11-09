# P3実カードマスター連携 — 2026-11-10

## 判定
**2026-11-10追補：正式P3と全テストは実行済み、90/90 PASS（skip 0）。** [正式統合・本番採用ゲート判定](P3_FORMAL_FULL_REGRESSION_20261110.md)。以下は追補前の独立スモーク履歴。

## 現物と独立検証
Drive `GPT/MasterDuel/DB/MD_CARD_MASTER_13948_PR2509_VALIDATION_ONLY_20261110.sqlite.zip` のローカル読み取り用コピーを解析した。ZIP SHA-256 `e81920a247631c66f1fdc04b500c27644c273dcc6b3741e07450755f652c29d5`、カード13,948件、日本語表示名重複1組、`inventory` 0件、integrity_check=ok、FK違反なし。

P1の `normalize_name` と同一のNFKC/casefold/空白除去規則を使った**独立SQLite照合スクリプト**で以下を確認（P3関数そのものではない）：

| ケース | 結果 |
|---|---|
| 灰流うらら3、増殖するＧ2、墓穴の指名者1 | 全件RESOLVED、適用候補 |
| 増殖するG 2 | 正規化RESOLVED |
| カオス・ソルジャー1 | AMBIGUOUS（2候補）、バッチ拒否 |
| 存在しない架空カード1 | UNRESOLVED、バッチ拒否 |
| 灰流うらら3＋カオス・ソルジャー1 | バッチ全体拒否 |
| 増殖するG 1＋増殖するＧ2 | DUPLICATE_CARD_ID、バッチ拒否 |
| 灰流うらら0 | 適用候補、変更前状態UNKNOWN/NULLであり既知の0枚とは異なる |

検証前後で所持・履歴の書込なし。

## 正式P3コードでの回帰を再現するテスト
`voice_staging/tests/test_catalog_integration.py` を追加。実モジュール `sqlite_store.Store`, `zip_store.archive.pack`, `voice_staging.preview` を利用し、公開Gitには架空カードfixtureだけを配置する。実カードを含むプライベートZIPによる追加スモークは環境変数 `MD_PRIVATE_REAL_CATALOG_ZIP` の指定時のみ走り、なければskipする。対象ファイルのバイト列をGitHubへ送らないこと。実データのテストは擬似ヘッド束縛に過ぎず実Drive HEADの真正性・更新承認を証明しない。

実行例（ローカル環境、`master-duel/` から）：
```bash
python -m unittest discover -s voice_staging/tests -p 'test_catalog_integration.py' -v
MD_PRIVATE_REAL_CATALOG_ZIP=/private/path/catalog.sqlite.zip MD_PRIVATE_REAL_CATALOG_ZIP_SHA256=e81920a247631c66f1fdc04b500c27644c273dcc6b3741e07450755f652c29d5 python -m unittest discover -s voice_staging/tests -p 'test_catalog_integration.py' -v
```

**注意:** 追加テストはこの監査環境で正式P1/P2/P3のPythonソース一式を直接checkoutできず未実行。構文チェックと、独立スモークはPASS。正式実行が必要であり、PASS件数を捏造しない。

## 本番採用判定
P0の`P0_DECISION.md`と`docs/P1_A_LIMITED_GATE_DESIGN.md`を再確認。P1-A1の実データ永続台帳・本文検索は権利・出典・MD独立検証が未解決でNO-GO。本検証ZIPは非公開で、効果全文・禁止制限・所持を含まないが、**この状態だけでP1-A1の権利ゲートを解除したとはみなさない**。本番 `MD_CURRENT_HEAD.json` は空DBのまま維持。

次に正式なテスト実行の証跡と、基本メタデータ限定の私的本番利用可否を明示的に再評価する。単一ライター・CASなしを維持。

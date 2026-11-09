# PR #2509 — 実JSONの独立クロスウォークと検証SQLite（2026-11-10）

## ステータス

**実データ取得・SHA固定・別実装による全件クロスウォーク・ローカルSQLite ZIP作成/再展開はPASS。PR #2509の改訂後コード自体の実JSON通し実行は未実施で、PRはDraftのまま。** 本番HEAD、Drive正本、P1-A1の判断は変更しない。

## 入力

Drive `GPT/MasterDuel/source` の2026-11-09固定原本2件をコネクタ経由でraw downloadし、ローカルでバイト単位SHA-256を計算。

- `master-duel-raw.json` 83,388,036 bytes、SHA-256 `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b` = 監査固定SHAと一致。
- `cards.json` 110,258,836 bytes、SHA-256 `5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7` = 一致。

## 実形式差

- MDモンスター9,114件：`card_type` 欠損、`types` は `Dragon / Effect` 等の**文字列**。魔法2,801・罠2,033は `card_type`。
- MDの `level` / `rank` / `atk` / `def` は**文字列**。cards JSONでは原則整数。 `?`（可変攻守）はSQLite `NULL` とする（0ではない）。
- MDの `race` は独立フィールドではなく `types` 先頭要素から抽出する。
- 元PRの `kind` の `'spell' in tokens(...)` はSpellcasterをSPELL扱いするため誤り。元PRの数値値比較は文字列と整数で不一致。修正をPRブランチへ投入済み。

## 独立全件クロスウォーク（元PR関数そのものの実行ではない）

- MD候補 13,948、OCG候補 14,416
- 完全一致 13,931、正規化 13、例外 4
- 結合済 13,948、未解決 0、KONAMI ID重複 0、日本語名欠損 0、MDレア不一致 0
- MONSTER 9,114 / SPELL 2,801 / TRAP 2,033
- N 5,318 / R 4,038 / SR 2,954 / UR 1,638
- `craftable=NO` 17、`UNKNOWN` 13,931
- 日本語表示名に重複が1組あるため、P3名称解決は該当名でAMBIGUOUS扱いを維持。

## 独立SQLite検証（元PR importerそのものの実行ではない）

旧初期ZIPのコピーに、KONAMI IDをキーに`cards`→`card_attributes`→`md_catalog`へ一括トランザクションで13,948件投入（効果文、禁止制限、所持情報は一切投入しない）。

- cards / card_attributes / md_catalog = 各13,948
- inventory / inventory_history = 各0
- `PRAGMA integrity_check` = ok
- `PRAGMA foreign_key_check` = 0件
- ZIP再圧縮、再展開、再SQLite整合性検査 = PASS
- 作成DB 8,904,704 bytes、ZIP 1,107,483 bytes
- ZIP SHA-256 `1a122dadd03c862c720c3564467bcc8442ef8dc05f10907f36a1a092b944a3b5`
- SQLite SHA-256 `483f31bbed1b3368c2665009c1cd20cc09030f4f8600295a2422ade8bf8aeee3`
- ローカル検証用成果物のみ。本番Drive HEADの変更・実データ本番昇格は **未実施**。

## PR #2509への処置

`card_master_import/importer.py` に実形式の種別、数値変換、未知攻守、race抽出対応。新たに架空fixtureの実形式回帰テストを追加。2026-11-10の独立実測とPRコード通し実行は別物であり、後者は未実施。独立実行の結果をもってPR改訂コードに無条件GOは出さない。

次の受入条件：**このPRの現在の`read_inputs`→`dry_run`→`convert`を、同じ固定SHAの実JSON2本で再実行し、出力整合性・再現性・冪等性を確認する**。公開GitHubに原JSON・実DB本体・カード本文は保存しない。P1-A1ゲートは別。

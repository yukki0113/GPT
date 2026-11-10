# M3 初期実装監査 — 日付付きMD規制とレア別CP（2026-11-10）

## 前提と実ソース監査

- 非公開Drive source/current.vector.json は 2026-11-05 候補215件。元ファイルSHA256 2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781。
- 非公開本番MDカードマスター13,948件と結合し、candidate ID存在 215/215、欠損0。データ取得と検証は読取専用。
- 元vectorは日付・215件のIDと値だけで、出典・FORMAT・ゲーム内確認の保証がない。新しい2026-11-05の適用予告自体は公式SNSで確認可能だが、215値の全件を公式確認済みとして保存しない。
- 原本のDB本番HEADは世代1、inventory/history 0件で変更していない。規制テーブルへの本番書き込みは実施しない。

## 実装と受入対象

regulation_m3/snapshots.py: strict versioned schema、日付・時点・MDフォーマット・規制 0/1/2/3・SHAと出典の検証。legacy vectorはCANDIDATE_ONLYへ変換し、未掲載をUNKNOWN、新しい未検証を過去のGAME_VERIFIEDで代用しない。同日複数スナップショットは曖昧扱い。

regulation_m3/evaluation.py: 保守的な既存デッキレシピ判定に検証済みの禁止制限だけを与え、所持数と採用可能枚数を結合。CP-N/R/SR/URを独立した通貨として見積もり、CP予算は通貨ごとに比較。候補CPルールやUNKNOWN所持なら確定のPASS/FAILを返さない。

regulation_m3/tests/test_m3.py: 検証済みと候補の切り分け、施行日・重複・日付逆転・未掲載UNKNOWN、0/1/2/3、所有 min、規制違反、候補CP、SR予算とN予算の非互換等の架空テストを追加。

## 未達・安全ルール

- 現行MDゲーム画面の規制全件検証は未完了。215件の候補値を実際の制限枚数として確定できない。
- 生成CP単価は候補と確認済みを分離し、未確定値での予算PASSを保証しない。カードごとの生成可否も未検証のものはUNKNOWN。
- 本番DBへのbanlist導入、非公開HEAD切替、ユーザー所持の登録は未実施。ユーザーに追加所持申告を求めずM3の基盤だけ先行する。
- レシピは入力されたもののみ評価。低レアテーマ自動発掘はM6。

## GitHub/CIの検証

- 実装コミット: c305415dd0efe1df339ab15b7ec20b98a0273520。mainへのfast-forwardとソースの読み戻しを確認。
- GitHub Actions: https://github.com/yukki0113/GPT/actions/runs/42749910295 — success。
- 既存110件＋M3新規13件＝123件。**失敗0・スキップ1**。スキップは非公開本番ZIPを公開CIへ送らない従来の実データ読取ケース。M3新規13件は全PASS。
- 実vector候補215件の内訳: 最大0枚 114件、1枚 77件、2枚 24件、3枚 0件（**全件未検証候補の集計**）。未掲載カードの許容枚数はUNKNOWN。
- GitHub Actionsで実非公開DBを読み込んだという意味ではない。実データ監査は別のローカル読取環境で実施。

## M3第2段階（2026-11-10）：非公開候補の安全なSQLite格納

- 正本HEADは M2 所持登録完了後の **generation 2**（`md-prod-002-inventory-five-20261110`）。前回監査の「generation 1・inventory 0」は当時の記録であり現在値ではない。
- 現行SQLite実読取：cards/md_catalog/card_texts 各 13,948、inventory 5、inventory_history 5、banlist_snapshots 0、banlist_entries 0、integrity_check=ok、外部キー違反0、HEAD/ZIP/SQLite SHAが一致。
- Driveの2026-11-05版候補vector 215件（0:114、1:77、2:24、3:0）、SHA256 `2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781` を使用。非公式独立ソースの掲載件数・施行日とも一致したが、値の個別公式照合は完了していない。
- `regulation_m3/catalog_store.py` を追加し、隔離されたSQLiteコピーへ候補をトランザクション投入するコード、同一ID/同日衝突検知、正規KONAMI ID照合、再送冪等、読み戻し集計を実装。**GAME_VERIFIEDはこの取込経路では拒否**。
- GitHub公開領域には規制候補215行の生データ、カード効果全文、個人の所持情報、非公開SQLiteは置かない。未掲載カードはUNKNOWNを維持。
- 2026-11-10の現行MD候補で「墓穴の指名者」は0枚という候補表示。所有1枚は消さず、規制によるデッキ採用不可と所有の違いを保守的に区別する。独立したMD攻略情報による禁止情報は確認できるが、本番スナップショットをゲーム内確認済みとは表現しない。
- 非公開DBへの候補格納・HEAD昇格、独立読み戻し、およびCI結果は各々実施後の記録に限る。保存前は本節だけを根拠に昇格済みとは扱わない。

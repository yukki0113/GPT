> **追補（2026-11-10 M3続編）**：この監査の下部にある「本番HEAD世代1」「所持未登録」は執筆時の履歴であり、現状は**世代2、所持5種類・9枚**。本番DBの規制表はなお空。新規M3 importer・DBローダーを追加し、未検証候補215件をSQLiteで持つ更新ZIPを作成可能にした。公開Gitに実カードの規制一覧、効果全文、私的所持データを載せない。
> 公開照合では、2026-11-05版の件数「禁止114/制限77/準制限24」が複数の独立サイトで一致（https://yugiohcardlist.com/banlist/master-duel/2026-11-05 / https://masterduel.online/en/banlist ）。これは集計数の一致に過ぎず、全215件の公式ゲーム内一致を保証しない。
> 2026-09-03付の「墓穴の指名者」禁止化は https://yugioh-starlight.com/archives/60027278.html に公式発表引用があり、11月版候補も0枚。所持している実物/アカウント上の1枚と、採用枚数上限0を分離。source crosscheckはGAME_VERIFIEDへの自動昇格ではない。
> M3 candidate ZIP作成処理はプレビューSHA照合、ID全件確認、SQLiteトランザクション、バックアップ・再展開・integrity、元の所持履歴不変を要求。Drive正本切替は別途バックアップと独立再取得が必要。元vectorの出典情報自体は欠如しているため、永続化はUNVERIFIED_SOURCE。

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

## 2026-11-10 M3-2候補SQLite格納の安全設計

- M2登録済み本番HEAD世代2（所持5カード・合計9枚、13,948カード・日本語効果）を最新親として使用。世代1の記載は過去の履歴。
- 禁止制限ソースは非公開Driveの `current.vector.json`、SHA256 `2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781`、2026-11-05施行候補215件（0:114、1:77、2:24）。
- 2026-11-05改訂の9変更は、Master Duel Meta（2026-10-26発表）と複数攻略サイトを用いて照合し、非公開vectorの対象カードID/値9件が改訂後の内容と一致。公開出典: https://mdm.app.duellinksmeta.com/articles/news/october-26-2026/master-duel-forbidden-list-update , https://game8.jp/yugioh-masterduel/423063 。**215件全体の確認には相当しない**。
- `regulation_m3/persistence.py` は `GAME_VERIFIED` の無根拠昇格を拒否し、`UNVERIFIED_SOURCE` のままSQLite v1 `banlist_snapshots` / `banlist_entries` へ追加する純粋処理。既存スナップショット・所持・カードマスター/効果本文・その他保護9テーブルの変更を拒否する。snapshot ID重複、未知ID、ZIP破損で失敗する。
- ZIP更新は新ファイルに限る。公開GitHub上のテストは架空カードだけを使用し、実215件一覧や効果・所持個票を格納しない。
- M3全体完了には、候補の全件MDゲーム内照合または信頼できる正式全件データと日付差分の完全性確認、そしてCP方針の出典/確認ステータス整備が残る。

## 2026-11-10 M3-2 独立再検証結果（並行書込回避）

- コードは GitHub コミット `0f5f03571e479b3a7d88b0bc99891aa66dae10fd` へ反映。Actions https://github.com/yukki0113/GPT/actions/runs/42756522689 で総数138テスト・失敗0・スキップ1。スキップは非公開本番ZIPに依存するテスト。
- Driveには別実行で作成済みの世代3「候補ZIP」とマニフェストが存在。**新たな重複ZIP作成やHEAD更新を実施せず**、既存候補を独立取得して読み戻した。
- 既存候補ZIP/SQLiteのSHAはマニフェストに完全一致、SQLite integrity=ok、外部キー違反0。出典vector SHAも既知値と一致。規制候補は215件、検証状態は `UNVERIFIED_SOURCE`。
- 世代2ソースと世代3候補の9保護テーブル（カードマスター・属性・MDレアリティ・日本語効果・所持/履歴/バッチ・デッキ）を全行比較し、差分0。規制の215件は元vectorとキーおよび枚数を全件照合し、215/215一致。
- **この監査時点の正本HEADは世代2のまま**。候補の存在は正本昇格を意味しない。別スレッドからの並行した候補/バックアップ操作が検出されたため、単一ライターの原則によりこのスレッドではHEADを切り替えない。
- 実際のMD禁止制限として「合法」「禁止確定」を一括断定するには、規制の確定出典の確認が引き続き必要。

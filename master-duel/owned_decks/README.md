# 所持デッキ音声登録 — private snapshot v1

公開GitHubには**コード・架空テストだけ**置く。実レシピ・発話・カード個票はGoogle Drive `GPT/MasterDuel/DB/` のprivate保存とする。既存本番HEAD (所持DB) は変更しない。

## データ形式

1デッキの1版 = JSON 1件。例はすべて架空カード。

```json
{
  "schema": "md-owned-deck-v1",
  "deck_id": "synthetic-evil-twin",
  "name": "架空イビルツイン",
  "aliases": ["イビルツイン"],
  "version": 1,
  "supersedes": null,
  "state": "STAGED",
  "entries": [
    {"section":"MAIN", "spoken_name":"架空A", "card_id":"synthetic:a", "quantity":40},
    {"section":"EXTRA", "spoken_name":"架空B", "card_id":"synthetic:b", "quantity":1}
  ]
}
```

- `deck_id` は同じデッキの更新で不変。混合型の区別は名前・aliases・任意variantで維持し、別デッキなら別deck_id。
- `version` は1から単調増加。2以降は直前版のsnapshot SHA256を`supersedes`に保持。古い版を削除しない。
- `STAGED` は中断・枚数不足・ID不明・EX超過でも保存できる。`CONFIRMED` は全カードID解決済み、MAIN40–60/EX15以下のみ。**CONFIRMED はゲーム合法性・所持照合の証明ではない**。
- `spoken_name`は原発話に対応。重複発話は音声スレッド側で原文・行番号・合算根拠をprivateチェックポイントに保持し、確定行では区画とcard_idで一意に集約する。
- 所持台帳への自動加算・更新は厳禁。デッキレシピには未所持カードがあってもよい。
- MD禁止制限・制約・所持枚数やレアリティは、構築時に最新HEADとM3/M4/M5を改めて照合する。

## ローカル検証と私的スナップショット

`master-duel/`から:

```sh
python -m unittest discover -s owned_decks/tests -v
python -m owned_decks validate --input /private/deck.json --db /private/master_duel.sqlite
python -m owned_decks save --input /private/deck.json --db /private/master_duel.sqlite --private-dir /private/decks
python -m owned_decks find --private-dir /private/decks --name イビルツイン
python -m owned_decks show --private-dir /private/decks --sha256 <64文字の実SHA>
```

`/private/decks`は事前に非公開ディレクトリとして作成。保存はSHA命名の不変JSON（0600）で、同一内容の再登録は冪等。これは**ローカルの検証・保存・検索コード**でありGoogle Drive自動接続ではない。Driveへの保存は認証済みChatGPT/Workコネクタから別途実行し、再取得とSHA一致で確認する。GitHub ActionsにDrive資格情報を渡さない。

## 音声スレッドの操作手順

1. ユーザーが「自分のイビルツインデッキを登録」と宣言したら、`deck_id`・variantを確定し、MAIN/EXを10件程度ずつ読み上げる。
2. 未解決カードと区画を確認し、途中終了なら`STAGED` JSONをprivate Driveへ保存・再取得。チェックポイント未成功を「保存済み」と扱わない。
3. 「読み上げ終了」は入力終了のみ。MAIN/EX枚数・カードID照合を見せ、ユーザーの**保存承認**を得てCONFIRMED JSONをprivate Driveに不変の新規ファイルとして保存する。
4. デッキ名、`deck_id`、version、SHA、private DriveファイルID、状態をまとめたprivate索引（例 `MD_OWNED_DECK_CATALOG.json`）へ追記。索引も別ファイルでバックアップし、単一ライターで更新後再取得する。前版は保持。
5. 検索室・構築室で「自分のイビルツインデッキ」と指定されたら、毎回private索引を取得し、名前・aliasesから候補を挙げ、選んだdeck_idの最新CONFIRMED版を取得。JSONのSHAとカードIDを照合してMAIN/EXを返す。見つからなければ未登録と明示する。STAGEDのみの場合は未完成と明記する。
6. 別デッキとの同名・複数variantがあれば候補一覧で区別する。索引をGitHubや会話メモリの固定IDだけで代用しない。

**現状**: v1ローカル検証・検索器を追加。ユーザーの実所持デッキはまだ未登録。private Drive catalog自動同期および本番SQLiteの`decks`/`deck_cards`書込器は未実装。実運用ではDriveコネクタ経由の保存・索引更新を要する。

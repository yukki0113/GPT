# P1 SQLite 基盤

標準 Python のみ。P1-A0 の名称正規化を使用する。架空データでのみ検証済み。実データの利用は P1-A1 NO-GO のまま。

`master-duel` から Python API `sqlite_store.Store.create(path)` で明示的に空 DB を初期化し、既存 DB は `Store(path)` で開く。最後に `close()` する。通常オープンはファイルを作成せず、スキーマ版と必須テーブル定義を検証する。`create` は空 DB を初期化し、既存 DB は同じ検証を行う。メソッドは `version`, `add_card`, `get_card`, `update_card`, `set_attributes`, `get_attributes`, `set_md_catalog`, `get_md_catalog`, `search_cards`, `resolve_name`, `get_inventory`, `set_inventory`, `batch_diff`, `history`, `undo_batch`, `integrity_check`。ID は変更不可。属性と MD 情報は `set_*` で指定フィールドを登録・更新できる。他の後続テーブルはスキーマのみ。

GPT からの JSON CLI 例（`db` はプライベートなローカルパス）:

```sh
printf '%s' '{"db":"/tmp/example.sqlite","operation":"initialize"}' | python -m sqlite_store
printf '%s' '{"db":"/tmp/example.sqlite","operation":"add_card","args":{"card_id":"fiction-1","konami_id":1001,"name":"架空竜"}}' | python -m sqlite_store
printf '%s' '{"db":"/tmp/example.sqlite","operation":"set_inventory","args":{"batch_id":"input-001","updates":[{"card_id":"fiction-1","owned_count":2}]}}' | python -m sqlite_store
printf '%s' '{"db":"/tmp/example.sqlite","operation":"undo_batch","args":{"batch_id":"input-001","undo_id":"undo-001"}}' | python -m sqlite_store
```

JSON 一件を標準入力から受け、`{"ok":true,"result":...}` または `{"ok":false,"error":...}` を返す。エラー時終了コードは 1。`resolve_name` は完全または NFKC/casefold/空白除去の一致候補を返し、複数候補は AMBIGUOUS。類似名推測はしない。呼び出し側が全件解決を確認してから ID 指定で一括更新する。

`owned_count` は非負整数または null（UNKNOWN）。設定は加算ではない。バッチ ID とソート済み内容で再送を照合し、同一内容は元の差分を返し、別内容は拒否する。再送は取り消し後や後続更新後でも状態を再適用しない。履歴には変更がない設定も記録する。取り消しは別バッチとして履歴に残す。同じ undo ID の再送は冪等。対象カードに後続更新があれば全件取り消しを拒否する。取り消しの取り消しは未対応。書き込みは `BEGIN IMMEDIATE` とロールバックで一括実行。

`cards` の論理 ID と一意の KONAMI ID を分離し、名称やパスコードをキーにしない。別イラストの関連付けは後続の明示的な版テーブルで扱う。`card_attributes`, `md_catalog`, `card_texts`, `banlist_snapshots`, `banlist_entries`, `inventory`, `inventory_batches`, `inventory_history`, `decks`, `deck_cards`, `schema_migrations` を設置。MD レアリティの出典は `MD:` を必須とし、生成可否は既定 UNKNOWN。禁止制限の行がない場合は UNKNOWN で、無制限を推論しない。P1-A0 の `canonical_id` に相当する名前を `card_id` とした。追加版管理・パック・意味検索は後続設計。`schema_migrations` の初期版は 1、それ以外の版は拒否する。

## P2 への受け渡し契約

P1 の入出力はローカル SQLite ファイルと JSON request/response のみ。Drive の取得・保存・ZIP は実装しない。P2 では、Drive 正本の取得と ZIP 検証、パストラバーサル防止、展開先の私的管理、スキーマ版と integrity/foreign-key 検査、書き込み競合検出、バックアップ・復旧、SQLite の一貫したバックアップと安全な ZIP 作成、更新前後の同一性確認、失敗時に正本を上書きしない条件を設計・検証してから接続する。DB と履歴には個人情報や権利対象本文が入りうるため Git、公開ログ、Issue に置かない。P0 の利用条件と P1-A1 ゲートは別途必要。

テスト（master-duel から）:

```sh
python -m unittest discover -s sqlite_store/tests -v
(cd p1_a0 && python -m unittest discover -s tests -v)
```

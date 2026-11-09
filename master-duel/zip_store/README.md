# P2 SQLite ZIP スナップショット

標準 Python のみ。P1-A1 は NO-GO。実カード本文・個人所持データ・既存 Drive ファイルをテストに使用しない。P2 はローカルとモックアダプターで検証済み。実 Drive コネクタの実装・正本参照の更新は含まない。

## インターフェース

`master-duel` から `zip_store.prepare(source_zip_bytes, parent_snapshot_id, snapshot_id, operation)` を呼ぶ。ZIP は `master_duel.sqlite` 一件のみ、圧縮 64 MiB・展開 256 MiB・圧縮率 1000 倍以内。名前、種類、暗号化、サイズ、CRC、SQLite スキーマ、integrity と foreign-key を検査。入力は変更せず一時ディレクトリで P1 `Store` を使用し、更新後チェック、SQLite backup API、ZIP 化、再展開とハッシュ検証を行う。圧縮率制限は極端に圧縮できる正当な DB も拒否しうるため、拡張時はサイズ制限と合わせて再評価する。

例（架空 ID）:

```python
from zip_store import prepare, publish, inspect
op = {'operation_id':'voice-001', 'operation_type':'SET_INVENTORY',
      'updates':[{'card_id':'fiction-001', 'owned_count':3}]}
result = prepare(zip_bytes, 'snapshot-001', 'snapshot-002', op)
print(result['diff'])
# 単一ライターを確保し、互換アダプターを用意した場合のみ:
manifest = publish(adapter, result, 'backup-001')
# 取り消しは新規操作 ID を使う:
undo = {'operation_id':'undo-001', 'operation_type':'UNDO_INVENTORY', 'batch_id':'voice-001'}
# prepare(result['zip'], 'snapshot-002', 'snapshot-003', undo)
```

名前による自動確定は行わない。`inspect(zip_bytes, 'search_cards', query=...)`、`get_inventory`, `history`, `batch_diff` は読み取り専用の一時コピーで P1 API を呼ぶ。`prepare` の返却値は `zip`（bytes）、`diff`、`manifest`。同一操作 ID の再送と衝突検査は P1 の契約に従い、再送は元の差分を返すだけで状態を再適用しない。未解決 ID は全更新を失敗させる。

manifest は親・新 snapshot ID、スキーマ版、入力・出力 ZIP/DB SHA-256、UTC 作成時刻、操作 ID・種別、検証状態、件数を持つ。カード名・効果本文・個別所持情報は含めない。`LOCAL_VERIFIED` はローカル検証のみ、`READBACK_VERIFIED` は新規保存後の独立読み戻しも成功したことを示す。呼び出し元が manifest を私的に永続保存し履歴として管理する。manifest 自体の保存・認証・正本指定の切替は未実装。

## 保存・競合契約

`storage_adapter.SnapshotAdapter` は `read_head() -> str`, `read(id) -> bytes`, `create(id, bytes) -> None` を要求する。`create` は既存 ID を上書きせず重複時に失敗し、`read` は独立に保存先から取得、曖昧な失敗や head 不明を例外にする必要がある。`MemoryAdapter` はテスト用。Drive 接続実装は未提供。コネクタに合わせて新規ファイル ID と snapshot ID の対応、確実な再取得、重複識別、head 観測を別途実装・検証すること。

`publish` は親の head と SHA を検査し、別 ID に元 ZIP のバックアップを作成・読み戻し、親を再確認し、別 ID に候補を作成・読み戻して ZIP/DB を検証し、最後に親を再確認する。元を上書き・削除せず、head を昇格しない。失敗時に新規のバックアップや未検証候補が残ることがあるため、削除せず ID・状況を記録して調査する。復旧は検証済みバックアップを読み戻して検証し、管理者が正本参照を切り替える手順で行う。

**単一ライターは運用で確保する。** 音声スレッドは候補作成のみ。head と SHA の再確認は観測した変更を検出するが、チェックと保存・昇格の間の競合を防止できない。条件付き更新やロックが未確認のため、複数ライターの安全性や正本昇格の原子性は保証しない。head を検証できない場合は中止し、候補を正本とみなさない。実 Drive 接続・権限・保存・読み戻しと参照切替の手順を別途検証するまでは本番運用しない。

## ChatGPT / Work 実地検証

1. 単一の作業スレッドを指定し、架空 DB の ZIP のみを新規テスト領域に用意する。元のユーザー DB、既存テスト、既存バックアップを変更しない。
2. GitHub の確定コミットを取得して Python 環境でテストを実行。コネクタによる ZIP 読み出しを bytes に変換し、`inspect` と `prepare` で架空 ID の差分とハッシュを確認する。
3. コネクタ向けアダプターを実装・検証し、新規ファイル作成と別要求での読み戻し、バックアップ・候補双方の SHA と DB 検査を確認する。条件付き操作がない場合、正本参照の切替は手動管理し、並行書き込みを禁止する。
4. 失敗・不明時は切替を中止して元ファイルを保持し、未検証候補を成功扱いにしない。P1-A1 の実データゲートは別途判定する。

テスト: `python -m unittest discover -s zip_store/tests -v`（`master-duel` から）。

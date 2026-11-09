# P3 音声入力ステージング

標準 Python。音声認識・Drive 更新は含まない。実データ取込は P1-A1 NO-GO。名前・枚数・発話・候補・プレビュー・DB は個人情報として私的領域にのみ置く。公開 Git、Issue、ログに記載しない。

`master-duel` から `voice_staging` を import。`parse_json` は `batch_id`, `scope`, `entries`（`raw_name`, `owned_count`）と任意 `source`, `utterance`, `supersedes` を受ける。`parse_csv(text, batch_id=..., scope=..., source=..., utterance=...)` のヘッダーは `raw_name,owned_count`。枚数は非負整数で設定値。文字列、真偽値、欠損は拒否する。カード名から ID は生成しない。

`save_batch(private_dir, batch)` は既存の私的ディレクトリへ batch ID の SHA-256 をファイル名にした JSON を排他的に作成する。ファイルのパーミッションは 0600。同じ ID・同一内容は冪等、異なる内容は拒否。`load_batch` で元入力を復元して再照合できる。訂正は元を消さず、**新しい batch ID** と `supersedes` に旧 ID を設定する。ファイル名のハッシュは暗号化ではなく、ディレクトリやバックアップのアクセス制御は利用者が確保する。入力の機密性や永続化は環境側の責任。

```python
from voice_staging import parse_json, save_batch, preview, prepare_update
batch = parse_json('{"batch_id":"voice-001","scope":"SYNTHETIC_TEST","entries":[{"raw_name":"架空竜","owned_count":3}]}')
save_batch(private_dir, batch)
# head と参照先 ZIP を正規経路で取得・検証した後に組み立てる。
target = {'head_name':'P2B_TEST_CURRENT_HEAD.json', 'scope':'SYNTHETIC_TEST',
          'snapshot_id':snapshot_id, 'zip_sha256':verified_zip_sha256}
p = preview(batch, zip_bytes, target)
# 人が全行と差分を確認し、明示的に確定した後:
if p['can_apply']:
    candidate = prepare_update(batch, zip_bytes, target, 'new-snapshot-id', p['preview_sha256'])
```

`preview` は P1 の正規化照合を使い `RESOLVED` / `UNRESOLVED` / `AMBIGUOUS`、候補、カード ID・名前、現在の状態・枚数、予定枚数、可否・理由を返す。同じ ID への複数行、既存バッチとの内容衝突、未解決・曖昧があれば全体を拒否。`prepare_update` はプレビューを同じ ZIP と入力から再計算しハッシュ一致を要求、P2 `prepare` を使いローカルの検証済み候補だけを返す。P1 のバッチ冪等性・一括ロールバック・履歴・P2 の検証を維持する。取り消しは P2 `UNDO_INVENTORY` の別操作 ID を使用する。プレビューのハッシュは変更検出であり、署名や人の承認の証明ではない。

## 正本と安全境界

`scope=PRODUCTION` は `MD_CURRENT_HEAD.json`、`scope=SYNTHETIC_TEST` は `P2B_TEST_CURRENT_HEAD.json` に限定し、バッチ・HEAD 名・scope の不一致、ZIP SHA 不一致を拒否する。架空テストを本番に流用しない。対象 HEAD の実ファイル取得、scope・snapshot ID・ZIP SHA の正確な抽出と真正性、最新性は呼び出し側が検証する必要があり、文字列を偽って渡された場合に本モジュールだけで実際の Drive の出所を証明できない。HEAD 名や ZIP のファイル名・更新時刻だけから正本を推定しない。

音声スレッドは候補を作成するのみ。作業スレッドが最新 HEAD と ZIP を再取得し、プレビュー確認後に候補を作る。Drive の保存・HEAD 更新は本モジュールの範囲外。P2 のバックアップ、独立読み戻し、単一ライター手順を別途遵守し、CAS がないため複数ライター安全性を主張しない。実マスターが未整備の間は未解決として保存し、P1-A1 の権利・出典ゲートが別途通るまで実データを取り込まない。

テスト: `python -m unittest discover -s voice_staging/tests -v`（master-duel から）。架空カードのみ。

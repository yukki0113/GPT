# P1-A0 第3段：スナップショット差分・回帰テスト監査（2026-11-09）

## 実行範囲
- `master-duel/p1_a0/snapshot_diff.py`: 手作り**架空データ限定**で、新旧カードスナップショットと禁止制限スナップショットの差分を比較する検査器。
- 実データ取得・Drive読み込み・本文保存/検索・アカウント操作・デッキ生成・実データ昇格は実施しない。
- GitHubの公開領域にゲーム由来の効果全文、ユーザー所持情報を含めない。

## 実装・入力契約
- `Dataset`のスナップショットID、ソースSHA-256（**形式のみ**を検査する値）を対比。
- カード追加・削除・属性変更、`canonical_id`のKONAMI ID再割当て（`CANONICAL_REBOUND`）、同じKONAMI IDに対する別canonical ID割当て（`KONAMI_REBOUND`）を検出。
- `verification`, `craftable`, `acquisition`, `password_variants`, MDレアリティ、名前変更はそれぞれ独立した差分フィールドとして保持。
- 同一snapshot IDと異なるsource SHA、同じSHAのはずなのに論理内容が異なるケースを拒否。入力順に依存しないSHA-256集計ハッシュを作成。
- 禁止制限は同一デッキ形式で発効日と0/1/2/3上限の変更・追加・規制一覧からの消失を比較。**消失は「3枚許可」ではなく要確認**。日付逆行と同一ID内容差替えを拒否。
- `REVIEW_REQUIRED`や`conflicts`は**呼び出し元が昇格を停止するための監査情報**。本ツール自体に更新・昇格機能はなく、自動的に本番状態を変更しない。

## 回帰テスト結果
- 実行コマンド: `cd /mnt/data/md_p1_a0_check && python -m unittest discover -s tests -q`
- 実測: **Ran 47 tests — OK**。
- テスト構成: 既存`test_catalog_contract.py`11件、既存`test_catalog_search.py`20件、追加`test_snapshot_diff.py`16件。
- テスト対象: 合成IDの追加・削除・名称/生成可否/所持ではなく検証状態/パスコード変更、canonical/KONAMI再割当て、同一IDのSHA変化、同じSHAでの内容変化、行順変化とレポートhash安定性、規制の新設・改訂・削除・未検証・形式差・日付逆行・ID使い回し。
- 本ターンにGitHubへ登録したBlob SHAと、テスト実行ファイルの`git hash-object`を一致確認:
  - `snapshot_diff.py` `21170936de2c0879e0d04bb8302779293e13fcb5`
  - `tests/test_snapshot_diff.py` `44bf269067fdf3906cec0f467965757e2767ff7f`
  - 既存`catalog_contract.py` `45baa5c08c92cdca3f74ca79b141e122d658af7a`
  - 既存`catalog_search.py` `4361e6b5dd88a28374041aa9ef67956b54f1f1d6`
  - 既存`tests/test_catalog_search.py` `a50e8ee3ff532df2b2575abc93a40b1b9b498673`

## 限界・次の判定
- `source_sha256`は**入力文字列と論理内容との相互整合**しか確認しておらず、Driveから取得した実ファイルのバイトハッシュを再計算する経路は含まない。
- 全件MD（13,948件）の運用データへ当てた実績はなく、47テストのPASSは**架空データの契約品質**を示すのみ。
- `P0-C`での公式MDゲーム内照合は**0/30件**、権利・利用条件の残課題あり。**P1-A1の実カード台帳・全文索引NO-GOは維持**。
- 最新スナップショットの公式確定や自動公開・書き込み機能の実装をこのテストが許可するものではない。

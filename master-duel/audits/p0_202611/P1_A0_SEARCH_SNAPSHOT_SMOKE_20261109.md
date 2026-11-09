# P1-A0 第2段：検索・禁止制限スナップショット契約監査（2026-11-09）

## 成果物
- `master-duel/p1_a0/catalog_search.py`: Git blob `4361e6b5dd88a28374041aa9ef67956b54f1f1d6`
- `master-duel/p1_a0/tests/test_catalog_search.py`: Git blob `a50e8ee3ff532df2b2575abc93a40b1b9b498673`
- 既存`catalog_contract.py`と既存11テストは変更なし。
- データはすべて手作り**架空fixture**。MDカード本文、原JSON、所持情報は使っていない。

## 機能
1. 日本語名のNFKC/大文字小文字/空白を正規化して**検索用にのみ**利用。元の表示名は不変。
2. 名称部分一致、種別、MDレアリティ上限、生成可否、入手経路、公式ゲーム確認済み状態をAND条件で適用。入力順を安定維持。
3. 規制スナップショットの`format_id`・`effective_on`を分離し、指定日以前の**最新施行日**を選択。イベントと通常ルールの混線を防止。
4. **未検証の新しいスナップショットは古い検証済み版へフォールバックしない**。`UNVERIFIED_SNAPSHOT`を返す。
5. カードID未掲載は**UNLISTED_UNKNOWN**として3枚と推定しない。競合する同日snapshotはAMBIGUOUS_SNAPSHOT、過去に対象版がない場合はNO_APPLICABLE_SNAPSHOT。
6. 明示的に未検証候補を照会した場合のみ`CANDIDATE_ONLY`を返し、`VERIFIED`とは区別。

## テスト
- 2026-11-09、Python `unittest discover -s tests -v`実行。
- **既存11件 + 新規20件 = 31/31 PASS**。
- 初回実行ではUNKNOWN検索テストの期待値が誤っており1件FAIL。架空fixtureにUNKNOWNが2件存在するのに1件と期待したことが原因。**期待値を修正して全31件PASSを再確認**。
- 実行ファイルの `git hash-object` を確認し、上記コード/テスト2ファイルのGit Blob SHAと完全一致している。
- **実MDゲーム公式確認0/30**、実JSON全件入力・カード効果検索・デッキ構築は未実施。合成データのPASSをゲーム内情報の確認とみなさない。

## 注意点
- `RegulationSnapshot.verified_in_game` は将来ゲーム内実測のprovenanceが必要な検証状態の契約値であり、公開JSONから自動で`True`にしない。
- 実カードに適用するには、ゲーム内独立検証、最新snapshotの候補選択、監査された変換と権利確認の別ゲートが必要。
- `Dataset.source_sha256` のバイトレベル一致検証は本試作では行っていない。文字列形式の検査のみ。
- 著作権のある日本語カード本文の全文索引をこの試作から生成しない。P1-A1: **NO-GO**。

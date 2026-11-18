# Gen9テーマ所属・盤面インスタンスの証跡台帳コンパイラ監査（2026-11-18）

## 実装と境界

前工程の `identity_material_evidence.py` は、ソースURLとSHAが申告されたとしても、生の出典バイトを検証せず `REVIEWED` 申告を受け取る構造だった。今回 `engine_m6/identity_source_ledger.py` を追加し、厳密な入力台帳から既存 `identity_evidence` 契約への**証跡束のコンパイル**を実装した。

- 出典文書台帳：`document_id`、`sha256`、`media_type`、`source_locator`、`review_status`。呼び出し側は出典文書の**実バイト**を `document_bytes[document_id]` として渡し、SHA-256を一致検証する。バイト欠如・改変・重複ID・レビュー未了は失敗。
- テーマ所属台帳：`card_id`、`archetype_label`、`is_member`、`document_id`、`review_status`。同じカードID×厳密なラベルの二重登録／矛盾を拒否。カード名部分一致からテーマ所属を自動推測しない。
- 盤面素材インスタンス台帳：`instance_id`、`card_id`、`board_snapshot_id`、`is_token`、`document_id`、`review_status`。素材の各出現位置にインスタンスIDを割当て、同一インスタンスの重複消費を拒否。2枚の同一カードIDは、同じIDの異なるインスタンスに限り別々に申告可能。異なる時点の盤面スナップショットやカードID相違を拒否。
- 文書のバイトSHAは出典の**同一性**だけを確認する。出典の公的権威、観測盤面の真正性、ユーザーの所持、モンスターの効果、MD裁定、素材同時確保は証明しない。 `REVIEWED` は入力者申告であって公式検証フラグではない。
- コンパイル結果は既存の `screen_structured_extra_materials(..., identity_evidence=...)` で利用可能。ただし出力は `REQUIRES_REVIEW` のままで `POSSIBLE_ON_PAPER` に昇格しない。既存の `proposed_routes` 契約、Gen9 SQLite保存値、ゲーム内適法性検証状態は不変。
- `NOT_TOKEN` の旧API互換性として、申告の `claim=False` が「トークンではない」を意味する。新台帳では `is_token=False` を明記し、コンパイラで旧表現へ写像する。この意味の違いを取り違えない。

## 正本の独立再検証

- Drive HEAD：Gen9、SQLite schema v4、HEAD SHA256 `e592b34198c290f59580976b6b861de893e6708596eb9df57b3b6e594643a66a`。
- ZIP：`MD_PROD_SNAPSHOT_009_STAGE2_EXTRA_MATERIALS_20261117.sqlite.zip`、SHA256 `0fa5fc724f8ab7671404f9297fb240095127840725d1bfd45a7431357467432f`。
- SQLite SHA256 `dd1e7d85c55b4ba764110af24d852d886abb787e72e18be2c5fd59ef57243411`。 `integrity_check=ok`、 `foreign_key_check` 0件、schema migrations 1–4。
- 私有Gen9 DBの既存UNPARSED XYZ/LINK 606件で日本語本文・素材ヘッダーのSHAを再計算：不一致0件。
- 厳密単独条件：XYZテーマ26件、LINKテーマ68件、LINK非トークン9件の計**103件**。これは**新たに公式出典や盤面ログで本人確認された素材数ではない**。
- 本番DB・ZIP・HEADに一切書き込まず、所持情報・個別日本語カード本文・カードIDをGitHubへ持ち出さない。

## 回帰テスト

`engine_m6/tests/test_identity_source_ledger.py` に**架空カード・架空文書だけ**を使った合成テストを追加。

- 正常なテーマ台帳をM6-5Bの任意証跡引数へ渡しても `screen=REQUIRES_REVIEW` のまま。
- 同じカードIDが2枚の場合、異なる盤面インスタンスIDが必要。同じインスタンスを2回指定、スナップショット不一致、インスタンスのカードID相違を拒否。
- トークンを示す申告の混在時は単純な `CLAIM_ALIGNED` にならない。
- 出典バイト不足・SHA不一致、出典／主張レビュー未了、所属根拠不足、同一カード所属の二重登録・矛盾、複合素材条件をフェイルクローズ。
- 実証されていない出典で「公式所属確認済み」や「ゲーム内召喚済み」に格上げする処理はない。

## 次のデータ収集ゲート

1. カードID×テーマ名の正式な所属表を、正本として扱う出典・取得時点・原ファイルとそのSHA・レビュアー判断を保持し、今回の台帳に流す。現在のモデルはあくまで**根拠を収容する器**。
2. トークン・盤面状態は、ゲーム内ログや信頼可能な盤面イベントと素材インスタンスの1対1対応を確認できる範囲だけ受け入れる。静的 `card_attributes` だけで非トークン性を確定しない。
3. 出典が確立するまでGen9内の103件を一括して「素材適格性verified」としない。次世代SQLite昇格の際のみ、単一ライター／独立読み戻し／保護テーブル件数確認を実施する。
